"""Concrete subprocess runtime for pinned Azimuth, CFD, and Cas-OFFinder sources."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel

from cellxp.domain.enums import ConfidenceBand, Strand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval

from .schemas import (
    CrisprRequest,
    CrisprResult,
    EditOutcomeRequest,
    EditOutcomeResult,
    Guide,
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
        contexts = rule_set_2_contexts(request)
        payload = json.dumps({"guides": request.guides, "contexts": contexts}).encode()
        completed = subprocess.run(
            self.azimuth_command, input=payload, capture_output=True, check=True, timeout=120
        )
        result = json.loads(completed.stdout)
        return GuideScoringResult.model_validate(result)

    def enumerate_off_targets(
        self, request: OffTargetRequest, *, assembly_index: AssemblyIndex
    ) -> OffTargetResult:
        reference = self._cas_reference_path(assembly_index)
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
        if not isinstance(request.target, GenomicInterval):
            raise ValueError("production guide design requires a resolved GenomicInterval target")  # noqa: TRY004
        if request.target.assembly not in {None, request.assembly}:
            raise ValueError("target interval assembly does not match the CRISPR request")
        if request.edit_type in {"base_edit", "prime_edit"}:
            raise ValueError(f"{request.edit_type} outcome model is not packaged")
        if request.cas not in {None, "SpCas9"} or request.pam not in {None, "NGG"}:
            raise ValueError("packaged guide enumeration supports SpCas9 with NGG PAM only")
        reference = read_fasta(self._fasta_path(assembly_index))
        candidates = enumerate_spcas9_candidates(
            reference, request.target, topology=assembly_index.topology
        )
        # The score/result contracts key by spacer; retain one reproducible locus per spacer.
        unique = {candidate.spacer: candidate for candidate in candidates}
        candidates = list(unique.values())
        if not candidates:
            return CrisprResult(
                guides=[], editing_system="SpCas9",
                rationale="no SpCas9 NGG sites with complete real 30-bp context in target",
            )
        contexts = {candidate.spacer: candidate.context for candidate in candidates}
        scoring = self.score_on_target(
            GuideScoringRequest(
                guides=list(contexts), organism=request.organism, assembly=request.assembly,
                model="rule_set_2", genomic_contexts=contexts,
            ),
            assembly_index=assembly_index,
        )
        off_targets = self.enumerate_off_targets(
            OffTargetRequest(
                guides=list(contexts), organism=request.organism, assembly=request.assembly,
            ),
            assembly_index=assembly_index,
        )
        version = ";".join(f"{item.name}@{item.revision}" for item in self.manifest.sources)
        guides = []
        for candidate in candidates:
            hits = off_targets.hits.get(candidate.spacer, [])
            specificity = 1.0 / (
                1.0 + sum(hit.cfd_score for hit in hits if hit.mismatches > 0)
            )
            on_target = scoring.scores[candidate.spacer]
            guides.append(Guide(
                spacer=candidate.spacer,
                pam=candidate.pam,
                strand=cast(Literal["+", "-"], candidate.strand.value),
                cut_site=candidate.cut_site,
                on_target_score=on_target,
                off_targets=hits,
                specificity_score=specificity,
                feasibility_notes=[
                    "SpCas9 NGG",
                    f"assembly topology={assembly_index.topology}",
                ],
                confidence=Confidence(
                    band=ConfidenceBand.MEDIUM,
                    basis="Rule Set 2 plus Cas-OFFinder/CFD; experimental validation required",
                ),
                provenance=Provenance(
                    tool="azimuth-rule-set-2+cas-offinder+crispor-cfd",
                    tool_version=version,
                    params={"pam": "NGG", "max_mismatches": 4},
                    inputs={
                        "organism": request.organism,
                        "assembly": request.assembly,
                        "chrom": request.target.chrom,
                        "target_start": request.target.start,
                        "target_end": request.target.end,
                        "strand": candidate.strand.value,
                        "context_sha256": hashlib.sha256(candidate.context.encode()).hexdigest(),
                    },
                ),
            ))
        guides.sort(
            key=lambda guide: (0.6 * guide.on_target_score + 0.4 * guide.specificity_score,
                               guide.spacer),
            reverse=True,
        )
        return CrisprResult(
            guides=guides[:request.num_guides],
            editing_system="SpCas9",
            rationale="ranked by Rule Set 2 on-target score and Cas-OFFinder/CFD specificity",
        )

    def predict_edit_outcomes(
        self, request: EditOutcomeRequest, *, assembly_index: AssemblyIndex
    ) -> EditOutcomeResult:
        raise ValueError(f"edit-outcome model for editor {request.editor!r} is not packaged")

    def _verify_executables(self) -> None:
        subprocess.run([self.cas_offinder], capture_output=True, timeout=30, check=False)
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
    def _fasta_path(index: AssemblyIndex) -> Path:
        for item in index.files:
            if item.role == "reference_fasta":
                return Path(os.getenv("CRISPR_INDEX_ROOT", "/indexes")) / item.path
        raise ValueError(f"assembly {index.assembly} lacks an attested reference FASTA")

    @classmethod
    def _cas_reference_path(cls, index: AssemblyIndex) -> Path:
        root = Path(os.getenv("CRISPR_INDEX_ROOT", "/indexes"))
        for item in index.files:
            if item.role == "off_target_index":
                return root / item.path
        # Cas-OFFinder v2.4 expects a directory containing FASTA files.
        return cls._fasta_path(index).parent

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


def rule_set_2_contexts(request: GuideScoringRequest) -> list[str]:
    """Return validated, assembly-derived 30-mers in guide order or fail closed."""
    if request.genomic_contexts is None:
        raise ValueError("Rule Set 2 requires real 30-bp genomic_contexts for every guide")
    contexts: list[str] = []
    for raw_guide in request.guides:
        guide = raw_guide.upper()
        context = request.genomic_contexts.get(raw_guide, "").upper()
        if len(guide) != 20 or set(guide) - set("ACGT"):
            raise ValueError("Rule Set 2 requires 20-bp unambiguous guide spacers")
        if len(context) != 30 or set(context) - set("ACGT"):
            raise ValueError("Rule Set 2 genomic context must be 30 unambiguous DNA bases")
        if context[4:24] != guide:
            raise ValueError("Rule Set 2 genomic context positions 5-24 must equal the guide")
        if context[25:27] != "GG":
            raise ValueError("Rule Set 2 genomic context must contain an NGG PAM at positions 25-27")
        contexts.append(context)
    return contexts


class SpCas9Candidate(BaseModel):
    spacer: str
    pam: str
    strand: Strand
    cut_site: int
    context: str


def read_fasta(path: Path) -> dict[str, str]:
    """Read an attested FASTA without aliasing or silently joining contigs."""
    sequences: dict[str, list[str]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            current = line[1:].split()[0]
            if not current or current in sequences:
                raise ValueError("FASTA contig names must be non-empty and unique")
            sequences[current] = []
        elif current is None:
            raise ValueError("FASTA sequence encountered before a header")
        else:
            sequence = line.upper()
            if set(sequence) - set("ACGTN"):
                raise ValueError(f"invalid DNA alphabet in FASTA contig {current}")
            sequences[current].append(sequence)
    if not sequences:
        raise ValueError("reference FASTA contains no contigs")
    return {name: "".join(parts) for name, parts in sequences.items()}


def enumerate_spcas9_candidates(
    reference: dict[str, str], target: GenomicInterval, *, topology: str
) -> list[SpCas9Candidate]:
    """Enumerate strand-oriented SpCas9 sites wholly inside a canonical target interval."""
    if target.chrom not in reference:
        raise ValueError(f"target contig {target.chrom!r} is absent from reference FASTA")
    sequence = reference[target.chrom]
    length = len(sequence)
    if not length or target.start >= length or target.end > length:
        raise ValueError("target coordinates exceed the attested FASTA contig")
    circular = topology == "circular"
    if not circular and target.start >= target.end:
        raise ValueError("origin-crossing targets require a circular assembly")
    positions = (
        list(range(target.start, target.end))
        if target.start < target.end
        else list(range(target.start, length)) + list(range(target.end))
    )
    included = set(positions)
    candidates: list[SpCas9Candidate] = []

    for start in positions:
        site_positions = _coordinate_run(start, 23, length, circular)
        context_positions = _coordinate_run(start - 4, 30, length, circular)
        if site_positions is None or context_positions is None or not set(site_positions) <= included:
            continue
        site = "".join(sequence[position] for position in site_positions)
        if site[21:23] == "GG":
            context = "".join(sequence[position] for position in context_positions)
            candidates.append(SpCas9Candidate(
                spacer=site[:20], pam=site[20:23], strand=Strand.PLUS,
                cut_site=(start + 17) % length, context=context,
            ))

    for pam_start in positions:
        site_positions = _coordinate_run(pam_start, 23, length, circular)
        context_positions = _coordinate_run(pam_start - 3, 30, length, circular)
        if site_positions is None or context_positions is None or not set(site_positions) <= included:
            continue
        site = "".join(sequence[position] for position in site_positions)
        if site[:2] == "CC":
            context = reverse_complement(
                "".join(sequence[position] for position in context_positions)
            )
            candidates.append(SpCas9Candidate(
                spacer=reverse_complement(site[3:23]),
                pam=reverse_complement(site[:3]),
                strand=Strand.MINUS,
                cut_site=(pam_start + 6) % length,
                context=context,
            ))
    return candidates


def _coordinate_run(
    start: int, width: int, length: int, circular: bool
) -> list[int] | None:
    if circular:
        return [(start + offset) % length for offset in range(width)]
    if start < 0 or start + width > length:
        return None
    return list(range(start, start + width))


def reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def create_runtime(
    manifest: CrisprWorkerManifest, indexes: IndexManifest
) -> ProductionCrisprRuntime:
    return ProductionCrisprRuntime(manifest, indexes)
