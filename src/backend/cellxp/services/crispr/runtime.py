"""Concrete subprocess runtime for pinned Azimuth, CFD, and Cas-OFFinder sources."""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from cellxp.domain.enums import Strand
from cellxp.domain.models import GenomicInterval

from .schemas import (
    CrisprRequest,
    CrisprResult,
    EditOutcomeRequest,
    EditOutcomeResult,
    GuideScoringRequest,
    GuideScoringResult,
    OffTarget,
    OffTargetRequest,
    OffTargetResult,
)
from .worker_contract import AssemblyIndex, CrisprWorkerManifest, IndexManifest


class ProductionCrisprRuntime:
    def __init__(self, manifest: CrisprWorkerManifest, indexes: IndexManifest) -> None:
        self.manifest = manifest
        self.indexes = indexes
        self.cas_offinder = os.getenv("CAS_OFFINDER_COMMAND", "/usr/local/bin/cas-offinder")
        self.azimuth_command = os.getenv(
            "AZIMUTH_COMMAND",
            "/opt/azimuth/bin/python /app/src/backend/cellxp/services/crispr/azimuth_legacy_score.py",
        ).split()
        cfd_root = Path(os.getenv("CFD_DATA_DIR", "/opt/crispr/cfd"))
        with (cfd_root / "mismatch_score.pkl").open("rb") as stream:
            self.mm_scores = pickle.load(stream, encoding="latin1")
        with (cfd_root / "pam_scores.pkl").open("rb") as stream:
            self.pam_scores = pickle.load(stream, encoding="latin1")
        self._verify_executables()

    def attest(self) -> dict[str, Any]:
        return {
            "source_revisions": {source.name: source.revision for source in self.manifest.sources},
            "algorithms": ["cas-offinder", "azimuth-rule-set-2", "crispor-cfd"],
        }

    def score_on_target(
        self, request: GuideScoringRequest, *, assembly_index: AssemblyIndex
    ) -> GuideScoringResult:
        payload = json.dumps({"guides": request.guides}).encode()
        completed = subprocess.run(
            self.azimuth_command, input=payload, capture_output=True, check=True, timeout=120
        )
        result = json.loads(completed.stdout)
        return GuideScoringResult.model_validate(result)

    def enumerate_off_targets(
        self, request: OffTargetRequest, *, assembly_index: AssemblyIndex
    ) -> OffTargetResult:
        reference = self._reference_path(assembly_index)
        with tempfile.TemporaryDirectory(prefix="cellxp-cas-offinder-") as temporary:
            input_path = Path(temporary) / "input.txt"
            output_path = Path(temporary) / "output.txt"
            lines = [str(reference), "N" * 20 + "NGG"]
            identifiers = {f"guide-{index}": guide for index, guide in enumerate(request.guides)}
            lines.extend(
                f"{guide.upper()}NNN {request.max_mismatches} guide-{index}"
                for index, guide in enumerate(request.guides)
            )
            input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            subprocess.run(
                [self.cas_offinder, str(input_path), os.getenv("CAS_OFFINDER_DEVICE", "C"),
                 str(output_path)],
                check=True, capture_output=True, timeout=1800,
            )
            hits: dict[str, list[OffTarget]] = {guide: [] for guide in request.guides}
            if output_path.exists():
                for raw in output_path.read_text(encoding="utf-8").splitlines():
                    identifier, query, observed, chrom, position, strand, mismatches = (
                        parse_cas_offinder_line(raw)
                    )
                    guide = identifiers.get(identifier, query[:-3])
                    if guide not in hits:
                        continue
                    start = int(position)
                    hits[guide].append(OffTarget(
                        locus=GenomicInterval(
                            assembly=request.assembly, chrom=chrom, start=start,
                            end=start + len(guide), strand=Strand(strand),
                        ),
                        mismatches=int(mismatches),
                        cfd_score=self._cfd(guide, observed),
                    ))
            return OffTargetResult(hits=hits)

    def design_guides(
        self, request: CrisprRequest, *, assembly_index: AssemblyIndex
    ) -> CrisprResult:
        return CrisprResult(
            guides=[], editing_system=request.cas or "SpCas9",
            rationale="target-sequence/PAM enumeration must be supplied by the CRISPR service",
        )

    def predict_edit_outcomes(
        self, request: EditOutcomeRequest, *, assembly_index: AssemblyIndex
    ) -> EditOutcomeResult:
        return EditOutcomeResult(efficiencies={}, outcome_model="not-packaged")

    def _verify_executables(self) -> None:
        subprocess.run([self.cas_offinder], capture_output=True, timeout=30)
        completed = subprocess.run(
            [*self.azimuth_command, "--version"], capture_output=True, check=True, timeout=30
        )
        revision = next(
            source.revision for source in self.manifest.sources
            if source.name == "azimuth-rule-set-2"
        )
        if revision not in completed.stdout.decode():
            raise RuntimeError("Azimuth command did not attest the pinned source revision")

    @staticmethod
    def _reference_path(index: AssemblyIndex) -> Path:
        for item in index.files:
            if item.role in {"reference_fasta", "off_target_index"}:
                return Path(os.getenv("CRISPR_INDEX_ROOT", "/indexes")) / item.path
        raise ValueError(f"assembly {index.assembly} lacks a reference/index artifact")

    def _cfd(self, guide: str, observed: str) -> float:
        target = observed.upper()
        spacer, pam = target[:20], target[-2:]
        score = 1.0
        reverse = {"A": "T", "C": "G", "G": "C", "T": "A", "U": "A"}
        for index, (wanted, found) in enumerate(zip(guide.replace("T", "U"),
                                                     spacer.replace("T", "U")), start=1):
            if wanted != found:
                key = f"r{wanted}:d{reverse[found]},{index}"
                score *= float(self.mm_scores[key])
        return max(0.0, min(1.0, score * float(self.pam_scores[pam])))


def parse_cas_offinder_line(raw: str) -> tuple[str, str, str, str, str, str, str]:
    """Parse current bulge-aware and pinned v2.4 Cas-OFFinder tabular output."""
    columns = raw.rstrip("\n").split("\t")
    if len(columns) >= 9:
        # ID, bulge type, query, observed, chromosome, position, strand, mismatches, bulge size.
        return columns[0], columns[2], columns[3], columns[4], columns[5], columns[6], columns[7]
    if len(columns) == 7:
        # Pinned v2.4.1: query, chromosome, position, observed, strand, mismatches, optional ID.
        return columns[6], columns[0], columns[3], columns[1], columns[2], columns[4], columns[5]
    if len(columns) == 6:
        return "", columns[0], columns[3], columns[1], columns[2], columns[4], columns[5]
    raise ValueError(f"unexpected Cas-OFFinder output with {len(columns)} columns")


def create_runtime(
    manifest: CrisprWorkerManifest, indexes: IndexManifest
) -> ProductionCrisprRuntime:
    return ProductionCrisprRuntime(manifest, indexes)
