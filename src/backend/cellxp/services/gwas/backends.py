"""Production and deterministic GWAS/QTL adapters (FR-14, GWS-1..5)."""

from __future__ import annotations

import os
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import Variant

from .schemas import (
    Association, ColocBatchResult, ColocRequest, FineMapRequest, FineMapResult,
    GwasRequest, GwasResult, LdRequest, LdResult,
)

T = TypeVar("T", bound=BaseModel)
_RETRYABLE = {429, 500, 502, 503, 504}


class HttpGwasBackend:
    """Typed client for a deployable GWAS statistical-computation worker."""

    name = "gwas_http"

    def __init__(self, base_url: str, *, token: str | None = None, timeout: float = 30.0,
                 retries: int = 2, version: str = "remote", client: httpx.Client | None = None):
        if not base_url.strip():
            raise ValueError("GWAS service base URL must not be empty")
        self.version, self.retries = version, retries
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout,
                                               headers=headers)

    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return self._post("/v1/associations", request, GwasResult)

    def compute_ld(self, request: LdRequest) -> LdResult:
        return self._post("/v1/ld", request, LdResult)

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        return self._post("/v1/fine-map", request, FineMapResult)

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        return self._post("/v1/coloc", request, ColocBatchResult)

    def attest(self) -> dict[str, str]:
        """Verify that the worker reports the deployment-pinned toolchain revision."""
        response = _request_with_retries(self._client, "GET", "/health", self.retries)
        payload = response.json()
        observed = str(payload.get("revision", ""))
        if self.version != "remote" and observed != self.version:
            raise RuntimeError(
                f"GWAS worker revision mismatch: expected {self.version}, got {observed or 'missing'}"
            )
        return {"status": str(payload.get("status", "unknown")), "revision": observed}

    def _post(self, path: str, request: BaseModel, result: type[T]) -> T:
        response = _request_with_retries(self._client, "POST", path, self.retries,
                                         json=request.model_dump(mode="json"))
        return result.model_validate(response.json())


class EbiGwasQtlBackend:
    """Read curated variant evidence from GWAS Catalog and eQTL Catalogue v3."""

    name = "ebi_gwas_eqtl"
    version = "gwas-rest-v2+eqtl-v3"

    def __init__(self, *, gwas_url: str = "https://www.ebi.ac.uk/gwas/rest/api/v2",
                 eqtl_url: str = "https://www.ebi.ac.uk/eqtl/api/v3", timeout: float = 30.0,
                 retries: int = 2, gwas_client: httpx.Client | None = None,
                 eqtl_client: httpx.Client | None = None):
        headers = {"Accept": "application/json"}
        self.retries = retries
        self._gwas = gwas_client or httpx.Client(base_url=gwas_url.rstrip("/"), timeout=timeout,
                                                  headers=headers)
        self._eqtl = eqtl_client or httpx.Client(base_url=eqtl_url.rstrip("/"), timeout=timeout,
                                                  headers=headers)

    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        if not isinstance(request.subject, Variant) or not request.subject.rsid:
            raise ValueError("live EBI lookup requires a normalized Variant with rsid")
        rsid = request.subject.rsid
        gwas = _request_with_retries(
            self._gwas, "GET", "/associations", self.retries,
            params={"rs_id": rsid, "size": 500},
        ).json()
        eqtl = _request_with_retries(
            self._eqtl, "GET", "/associations", self.retries,
            params={"rsid": rsid, "size": 500},
        ).json()
        records = [*_parse_gwas(gwas, rsid), *_parse_eqtl(eqtl, rsid, request.tissues)]
        if request.traits:
            wanted = {item.casefold() for item in request.traits}
            records = [item for item in records if any(term in item.trait.casefold()
                                                        for term in wanted)]
        return GwasResult(
            associations=records,
            confidence=Confidence(band=ConfidenceBand.HIGH if records else ConfidenceBand.UNKNOWN,
                                  basis="curated EBI catalog records"),
            provenance=Provenance(tool=self.name, tool_version=self.version,
                                  inputs={"rsid": rsid}, nondeterministic=True),
            coverage_note=None if records else f"no GWAS/eQTL records found for {rsid}",
        )

    def compute_ld(self, request: LdRequest) -> LdResult:
        raise NotImplementedError("EBI evidence adapter does not compute LD; use gwas_http")

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        raise NotImplementedError("EBI evidence adapter does not fine-map; use gwas_http")

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        raise NotImplementedError("EBI evidence adapter does not run coloc; use gwas_http")


class OpenTargetsGwasBackend:
    """Read variant-to-disease evidence from the versioned Open Targets GraphQL API.

    Open Targets does not provide the regional summary statistics needed for LD, SuSiE, or coloc;
    those operations deliberately remain worker-only instead of fabricating statistical results.
    """

    name = "open_targets"

    def __init__(
        self,
        *,
        base_url: str = "https://api.platform.opentargets.org/api/v4/graphql",
        release: str = "live",
        timeout: float = 30.0,
        retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self.version = release
        self.retries = retries
        self._endpoint = base_url
        self._client = client or httpx.Client(
            timeout=timeout, headers={"Accept": "application/json"}
        )

    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        if not isinstance(request.subject, Variant) or not request.subject.rsid:
            raise ValueError("Open Targets lookup requires a normalized Variant with rsid")
        rsid = request.subject.rsid
        mapping_response = _request_with_retries(
            self._client,
            "POST",
            self._endpoint,
            self.retries,
            json={"query": _OPEN_TARGETS_MAP_QUERY, "variables": {"terms": [rsid]}},
        )
        mapping_payload = mapping_response.json()
        _raise_graphql_error(mapping_payload)
        mappings = mapping_payload.get("data", {}).get("mapIds", {}).get("mappings", [])
        hits = mappings[0].get("hits", []) if mappings else []
        variant_ids = [str(hit["id"]) for hit in hits if hit.get("entity") == "variant"]
        records: list[Association] = []
        for variant_id in variant_ids[:4]:
            response = _request_with_retries(
                self._client, "POST", self._endpoint, self.retries,
                json={"query": _OPEN_TARGETS_QUERY, "variables": {"variantId": variant_id}},
            )
            payload = response.json()
            _raise_graphql_error(payload)
            records.extend(_parse_open_targets(payload, rsid, self.version))
        if request.traits:
            wanted = {term.casefold() for term in request.traits}
            records = [record for record in records if any(term in record.trait.casefold()
                                                              for term in wanted)]
        return GwasResult(
            associations=records,
            confidence=Confidence(
                band=ConfidenceBand.MEDIUM if records else ConfidenceBand.UNKNOWN,
                basis="Open Targets curated variant-to-disease evidence",
            ),
            provenance=Provenance(
                tool=self.name,
                tool_version=self.version,
                inputs={"rsid": rsid},
                citations=["https://platform.opentargets.org/"],
                nondeterministic=self.version == "live",
            ),
            coverage_note=None if records else f"no Open Targets records found for {rsid}",
        )

    def compute_ld(self, request: LdRequest) -> LdResult:
        raise NotImplementedError("Open Targets does not compute LD; use gwas_http")

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        raise NotImplementedError("Open Targets does not expose runnable summary statistics")

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        raise NotImplementedError("Open Targets does not run coloc; use gwas_http")


class DeterministicGwasBackend:
    """Offline empty-evidence fallback; deterministic and explicit, never fabricated."""

    name = "deterministic_empty"
    version = "1"

    def lookup_associations(self, request: GwasRequest) -> GwasResult:
        return GwasResult(confidence=Confidence(band=ConfidenceBand.UNKNOWN,
                                                basis="offline fallback has no catalog data"),
                          provenance=Provenance(tool=self.name, tool_version=self.version),
                          coverage_note="offline deterministic backend; no catalog queried")

    def compute_ld(self, request: LdRequest) -> LdResult:
        return LdResult(population=request.population, panel="none",
                        assumptions=["offline fallback has no LD panel"])

    def fine_map(self, request: FineMapRequest) -> FineMapResult:
        return FineMapResult(assumptions=["offline fallback does not run SuSiE"])

    def coloc(self, request: ColocRequest) -> ColocBatchResult:
        return ColocBatchResult(assumptions=["offline fallback does not run coloc"])


def gwas_backend_from_environment():  # noqa: ANN201
    mode = os.getenv("GWAS_BACKEND", "none").strip().lower()
    timeout = float(os.getenv("GWAS_SERVICE_TIMEOUT_SECONDS", "30"))
    retries = int(os.getenv("GWAS_SERVICE_RETRIES", "2"))
    if mode == "none":
        return None
    if mode == "deterministic":
        return DeterministicGwasBackend()
    if mode == "ebi":
        return EbiGwasQtlBackend(gwas_url=os.getenv("GWAS_CATALOG_URL",
                                                    "https://www.ebi.ac.uk/gwas/rest/api/v2"),
                                 eqtl_url=os.getenv("EQTL_CATALOG_URL",
                                                   "https://www.ebi.ac.uk/eqtl/api/v3"),
                                 timeout=timeout, retries=retries)
    if mode == "open_targets":
        return OpenTargetsGwasBackend(
            base_url=os.getenv(
                "OPEN_TARGETS_GRAPHQL_URL",
                "https://api.platform.opentargets.org/api/v4/graphql",
            ),
            release=os.getenv("OPEN_TARGETS_RELEASE", "live"),
            timeout=timeout,
            retries=retries,
        )
    if mode == "http":
        url = os.getenv("GWAS_SERVICE_URL", "").strip()
        if not url:
            raise ValueError("GWAS_BACKEND=http requires GWAS_SERVICE_URL")
        return HttpGwasBackend(url, token=os.getenv("GWAS_SERVICE_TOKEN") or None,
                               timeout=timeout, retries=retries,
                               version=os.getenv("GWAS_SERVICE_VERSION", "remote"))
    raise ValueError(f"unknown GWAS_BACKEND {mode!r}")


def _request_with_retries(client: httpx.Client, method: str, path: str, retries: int,
                          **kwargs: Any) -> httpx.Response:
    for attempt in range(retries + 1):
        try:
            response = client.request(method, path, **kwargs)
            if response.status_code not in _RETRYABLE or attempt == retries:
                response.raise_for_status()
                return response
        except httpx.TransportError:
            if attempt == retries:
                raise
        time.sleep(0.05 * (2 ** attempt))
    raise AssertionError("retry loop exhausted")


def _items(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    value: Any = payload
    for key in keys:
        value = value.get(key, {}) if isinstance(value, dict) else {}
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    for key in ("items", "results", "associations"):
        if isinstance(payload.get(key), list):
            return payload[key]
    return []


def _parse_gwas(payload: Any, rsid: str) -> list[Association]:
    output = []
    for item in _items(payload, "_embedded", "associations"):
        study = item.get("study") or item.get("studyAccession") or item.get("accession_id") or {}
        accession = str(study.get("accessionId") if isinstance(study, dict) else study or "unknown")
        trait = item.get("diseaseTrait") or item.get("trait") or item.get("efo_traits") or {}
        if isinstance(trait, list):
            trait = trait[0] if trait else {}
        trait_name = str((trait.get("trait") or trait.get("efo_trait"))
                         if isinstance(trait, dict) else trait or "unspecified trait")
        p = item.get("p_value") or item.get("pvalue") or item.get("pValue")
        if p is None:
            continue
        pmid = item.get("pubmed_id") or item.get("pubmedId")
        citations = [f"PMID:{pmid}"] if pmid else [accession]
        allele = item.get("riskAllele") or item.get("snp_effect_allele")
        if isinstance(allele, list):
            allele = allele[0] if allele else None
        output.append(Association(trait=trait_name, variant_id=rsid,
                                  beta=_float(item.get("beta")), p_value=float(p),
                                  effect_allele=allele,
                                  study_accession=accession, citations=citations,
                                  source="NHGRI-EBI GWAS Catalog", source_release="live"))
    return output


def _parse_eqtl(payload: Any, rsid: str, tissues: list[str] | None) -> list[Association]:
    wanted = {item.casefold() for item in tissues or []}
    output = []
    for item in _items(payload):
        tissue = str(item.get("tissue") or item.get("study_label") or item.get("dataset_id") or
                     "unspecified tissue")
        if wanted and not any(term in tissue.casefold() for term in wanted):
            continue
        p = item.get("pvalue") or item.get("p_value")
        if p is None:
            continue
        dataset = str(item.get("dataset_id") or item.get("study_id") or "eQTL-Catalogue")
        gene = str(item.get("gene_id") or item.get("molecular_trait_id") or "molecular trait")
        output.append(Association(trait=f"eQTL: {gene} ({tissue})", variant_id=rsid,
                                  beta=_float(item.get("beta")), p_value=float(p),
                                  effect_allele=item.get("alt"), study_accession=dataset,
                                  citations=[dataset], source="eQTL Catalogue", source_release="v3"))
    return output


def _float(value: Any) -> float | None:
    if value in (None, "", "-", "NR"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_OPEN_TARGETS_MAP_QUERY = """
query CellXPMapVariant($terms: [String!]!) {
  mapIds(queryTerms: $terms) { mappings { term hits { id entity name } } }
}
"""

_OPEN_TARGETS_QUERY = """
query CellXPVariantEvidence($variantId: String!) {
  variant(variantId: $variantId) {
    id
    credibleSets(page: {index: 0, size: 500}) {
      rows {
        studyId pValueMantissa pValueExponent beta sampleSize
        study { traitFromSource diseases { id name } }
      }
    }
  }
}
"""


def _parse_open_targets(payload: Any, rsid: str, release: str) -> list[Association]:
    variant = payload.get("data", {}).get("variant") if isinstance(payload, dict) else None
    rows = ((variant or {}).get("credibleSets") or {}).get("rows", [])
    records: list[Association] = []
    for row in rows:
        study = row.get("study") or {}
        diseases = study.get("diseases") or []
        disease = diseases[0] if diseases else {}
        trait = study.get("traitFromSource") or disease.get("name")
        study_id = row.get("studyId")
        mantissa = _float(row.get("pValueMantissa"))
        exponent = row.get("pValueExponent")
        if not trait or not study_id or mantissa is None or exponent is None:
            continue
        records.append(
            Association(
                trait=str(trait).strip(),
                variant_id=rsid,
                beta=_float(row.get("beta")),
                p_value=mantissa * (10 ** int(exponent)),
                study_accession=str(study_id),
                citations=[str(study_id)],
                source="Open Targets Platform",
                source_release=release,
                sample_size=row.get("sampleSize"),
            )
        )
    return records


def _raise_graphql_error(payload: dict[str, Any]) -> None:
    if payload.get("errors"):
        raise RuntimeError(f"Open Targets GraphQL error: {payload['errors'][0].get('message')}")
