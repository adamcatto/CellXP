"""Deterministic edge normalization for the supervisor preamble (FR-1, FR-9/10)."""

from __future__ import annotations

import re

from cellxp.agent.state import AgentState, NormalizedInputs, RawInput, RunError
from cellxp.domain.coordinates import interval_to_canonical
from cellxp.domain.enums import CoordinateSystem
from cellxp.domain.errors import DomainValidationError
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import parse_fasta
from cellxp.domain.validators.sequences import validate_sequence
from cellxp.domain.variants import detect_variant_notation, normalize_variant, parse_rsid

_RSID_RE = re.compile(r"\brs\d+\b", re.IGNORECASE)
_INTERVAL_RE = re.compile(r"\b(?P<chrom>(?:chr)?[A-Za-z0-9_.]+):(?P<start>\d+)-(?P<end>\d+)\b")
_VCF_RE = re.compile(
    r"\b(?P<chrom>(?:chr)?[A-Za-z0-9_.]+)[:\s](?P<pos>\d+)[:\s]"
    r"(?P<ref>[ACGTNacgtn]+)[:>\s](?P<alt>[ACGTNacgtn]+)\b"
)
_HGVS_RE = re.compile(r"\b[A-Za-z0-9_.]+:g\.\d+[ACGTNacgtn]+>[ACGTNacgtn]+\b")


def _parse_interval(value: str) -> GenomicInterval:
    match = _INTERVAL_RE.fullmatch(value.strip())
    if match is None:
        raise DomainValidationError(
            "interval must use chrom:start-end (1-based inclusive)", field="interval", value=value
        )
    start, end = interval_to_canonical(
        int(match["start"]), int(match["end"]), CoordinateSystem.ONE_BASED_INCLUSIVE
    )
    if start >= end:
        raise DomainValidationError(
            "interval end must be greater than or equal to start", field="interval", value=value
        )
    return GenomicInterval(chrom=match["chrom"], start=start, end=end)


def _append_text_signals(text: str, normalized: NormalizedInputs) -> None:
    """Extract only high-precision structured tokens from prose; never guess gene symbols."""
    for rsid in _RSID_RE.findall(text):
        canonical = parse_rsid(rsid)
        if canonical not in normalized.identifiers:
            normalized.identifiers.append(canonical)
    for match in _HGVS_RE.finditer(text):
        variant = normalize_variant(match.group(0))
        if variant not in normalized.variants:
            normalized.variants.append(variant)
    for match in _VCF_RE.finditer(text):
        raw = f"{match['chrom']} {match['pos']} {match['ref']} {match['alt']}"
        variant = normalize_variant(raw)
        if variant not in normalized.variants:
            normalized.variants.append(variant)
    for match in _INTERVAL_RE.finditer(text):
        interval = _parse_interval(match.group(0))
        if interval not in normalized.intervals:
            normalized.intervals.append(interval)


def run(state: AgentState) -> dict[str, object]:
    existing = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
    normalized = NormalizedInputs(organism=existing.organism, assembly=existing.assembly)
    errors: list[RunError] = []
    raw_items = [RawInput.model_validate(item) for item in state.get("raw_inputs", [])]

    if state.get("user_query"):
        try:
            _append_text_signals(state["user_query"], normalized)
        except DomainValidationError as exc:
            errors.append(RunError(kind=type(exc).__name__, message=str(exc)))

    for item in raw_items:
        value = item.value or ""
        try:
            if item.kind == "file":
                raise DomainValidationError(
                    "uploaded files must be resolved to text by the API before normalization",
                    field="file_ref",
                    value=item.file_ref,
                )
            if item.kind == "text":
                _append_text_signals(value, normalized)
            elif item.kind == "sequence":
                records = (
                    parse_fasta(value)
                    if value.lstrip().startswith(">")
                    else [validate_sequence(value)]
                )
                normalized.sequences.extend(records)
            elif item.kind == "variant":
                notation = detect_variant_notation(value)
                if notation.value == "rsid":
                    normalized.identifiers.append(parse_rsid(value))
                else:
                    normalized.variants.append(normalize_variant(value))
            elif item.kind == "interval":
                normalized.intervals.append(_parse_interval(value))
            elif item.kind == "identifier":
                identifier = value.strip()
                if not identifier:
                    raise DomainValidationError("identifier must not be empty", field="identifier")
                normalized.identifiers.append(identifier)
        except (DomainValidationError, ValueError) as exc:
            errors.append(
                RunError(
                    kind=type(exc).__name__,
                    message=f"Could not normalize input {item.id}: {exc}",
                    recoverable=True,
                )
            )

    if any(sequence.seq != sequence.seq.replace("N", "") for sequence in normalized.sequences):
        normalized.warnings.append("One or more sequences contain ambiguous IUPAC bases.")

    update: dict[str, object] = {"normalized_inputs": normalized}
    if errors:
        update["errors"] = errors
    return update
