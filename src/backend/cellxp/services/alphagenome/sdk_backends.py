"""Packaged adapters for the pinned official AlphaGenome and Evo 2 SDKs."""

from __future__ import annotations

import os
from typing import Any

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence

from .schemas import (
    AssayDelta,
    SequenceScoringRequest,
    SequenceScoringResult,
    SpliceEffectRequest,
    SpliceEffectResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffect,
    VariantEffectRequest,
    VariantEffectResult,
)
from .worker_common import WorkerManifest

_SUPPORTED_WINDOWS = (16_384, 131_072, 524_288, 1_048_576)


def _chromosome(value: str) -> str:
    return value if value.startswith("chr") else f"chr{value}"


def _organism(name: str, dna_client: Any) -> Any:
    if name == "Homo sapiens":
        return dna_client.Organism.HOMO_SAPIENS
    if name == "Mus musculus":
        return dna_client.Organism.MUS_MUSCULUS
    raise ValueError(f"AlphaGenome SDK does not support organism {name!r}")


def _output_types(assays: list[str] | None, dna_client: Any) -> list[Any]:
    aliases = {
        "ATAC": "ATAC", "ATAC_SEQ": "ATAC", "CAGE": "CAGE", "DNASE": "DNASE",
        "RNA_SEQ": "RNA_SEQ", "CHIP_HISTONE": "CHIP_HISTONE", "CHIP_TF": "CHIP_TF",
        "SPLICE_SITES": "SPLICE_SITES", "SPLICE_SITE_USAGE": "SPLICE_SITE_USAGE",
        "SPLICE_JUNCTIONS": "SPLICE_JUNCTIONS", "CONTACT_MAPS": "CONTACT_MAPS",
        "PROCAP": "PROCAP",
    }
    names = assays or ["RNA_SEQ"]
    try:
        return [getattr(dna_client.OutputType, aliases[name.upper()]) for name in names]
    except KeyError as exc:
        raise ValueError(f"unsupported AlphaGenome assay {exc.args[0]!r}") from exc


def _window(center: int, width: int) -> tuple[int, int]:
    if width not in _SUPPORTED_WINDOWS:
        raise ValueError(f"AlphaGenome window must be one of {_SUPPORTED_WINDOWS}; got {width}")
    start = max(0, center - width // 2)
    return start, start + width


class AlphaGenomeSdkBackend:
    """Map CellXP requests onto AlphaGenome 0.6.1's documented client methods."""

    version = "alphagenome==0.6.1"

    def __init__(
        self, client: Any, *, genome: Any, dna_client: Any, variant_scorers: Any
    ) -> None:
        self.client = client
        self.genome = genome
        self.dna_client = dna_client
        self.variant_scorers = variant_scorers

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        organism = _organism(request.organism, self.dna_client)
        wanted_assays = {item.upper() for item in request.assays or []}
        wanted_tissues = {item.lower() for item in request.tissues or []}
        effects: list[VariantEffect] = []
        for variant in request.variants:
            width = request.window_bp or 131_072
            start, end = _window(variant.pos, width)
            interval = self.genome.Interval(_chromosome(variant.chrom), start, end)
            sdk_variant = self.genome.Variant(
                chromosome=_chromosome(variant.chrom), position=variant.pos + 1,
                reference_bases=variant.ref.upper(), alternate_bases=variant.alt.upper(),
            )
            scores = self.client.score_variant(
                interval=interval, variant=sdk_variant, organism=organism
            )
            table = self.variant_scorers.tidy_scores(scores)
            rows = [] if table is None else table.to_dict("records")
            deltas: list[AssayDelta] = []
            for row in rows:
                assay = str(row.get("output_type") or row.get("variant_scorer") or "unknown")
                tissue = row.get("biosample_name") or row.get("gtex_tissue") or row.get("ontology_curie")
                if wanted_assays and assay.upper() not in wanted_assays:
                    continue
                if wanted_tissues and str(tissue).lower() not in wanted_tissues:
                    continue
                value = float(row["raw_score"])
                deltas.append(AssayDelta(
                    assay=assay, tissue=str(tissue) if tissue is not None else None,
                    value=value, direction="up" if value > 0 else "down" if value < 0 else "none",
                ))
            deltas.sort(key=lambda item: abs(item.value), reverse=True)
            effects.append(VariantEffect(
                variant_id=f"{variant.chrom}:{variant.pos + 1}:{variant.ref}>{variant.alt}",
                deltas=deltas, top_effects=deltas[:20],
                confidence=Confidence(
                    band=ConfidenceBand.MEDIUM,
                    basis="AlphaGenome raw recommended-scorer outputs; not a calibrated probability",
                ),
            ))
        return VariantEffectResult(per_variant=effects)

    def predict_tracks(self, request: TrackPredictionRequest) -> TrackPredictionResult:
        width = request.interval.end - request.interval.start
        if width not in _SUPPORTED_WINDOWS:
            raise ValueError(f"AlphaGenome interval width must be one of {_SUPPORTED_WINDOWS}")
        interval = self.genome.Interval(
            _chromosome(request.interval.chrom), request.interval.start, request.interval.end,
            strand=request.interval.strand.value,
        )
        requested = _output_types(request.assays, self.dna_client)
        ontology_terms = [item for item in request.tissues or [] if ":" in item] or None
        output = self.client.predict_interval(
            interval=interval, organism=_organism(request.organism, self.dna_client),
            requested_outputs=requested, ontology_terms=ontology_terms,
        )
        tracks: dict[str, list[float]] = {}
        for output_type in requested:
            track = output.get(output_type)
            if track is None:
                continue
            values = track.values
            if getattr(values, "ndim", 1) > 1:
                values = values.mean(axis=tuple(range(1, values.ndim)))
            tracks[output_type.name] = [float(value) for value in values.reshape(-1).tolist()]
        return TrackPredictionResult(
            tracks=tracks, model=self.version,
            confidence=Confidence(
                band=ConfidenceBand.MEDIUM,
                basis="AlphaGenome predicted tracks; confidence is qualitative",
            ),
        )

    def score_splicing(self, request: SpliceEffectRequest) -> SpliceEffectResult:
        del request
        raise NotImplementedError(
            "AlphaGenome's generic SDK scores do not map to CellXP's calibrated four-way "
            "donor/acceptor gain/loss contract without a pinned scorer policy"
        )


class Evo2SdkBackend:
    """Map sequence likelihood/embedding requests to Evo2 0.6.0's official SDK."""

    version = "evo2==0.6.0:evo2_7b"

    def __init__(self, model: Any, *, torch_module: Any | None = None) -> None:
        self.model = model
        self.torch = torch_module

    def score_sequences(self, request: SequenceScoringRequest) -> SequenceScoringResult:
        sequences = [sequence.upper() for sequence in request.sequences]
        if any(not sequence or set(sequence) - set("ACGTN") for sequence in sequences):
            raise ValueError("Evo 2 sequences must use the DNA alphabet A/C/G/T/N")
        scores = [float(value) for value in self.model.score_sequences(
            sequences,
            batch_size=int(os.getenv("EVO2_BATCH_SIZE", "1")),
            reduce_method="mean",
            average_reverse_complement=True,
        )]
        embeddings = None
        if request.scoring_type == "embedding":
            if self.torch is None:
                raise RuntimeError("torch is required for Evo 2 embedding extraction")
            layer = os.getenv("EVO2_EMBEDDING_LAYER", "blocks.28.mlp.l3")
            embeddings = []
            for sequence in sequences:
                input_ids = self.torch.tensor(
                    self.model.tokenizer.tokenize(sequence), dtype=self.torch.int
                ).unsqueeze(0).to("cuda:0")
                _, extracted = self.model(
                    input_ids, return_embeddings=True, layer_names=[layer]
                )
                vector = extracted[layer].detach().float().mean(dim=1).cpu().tolist()[0]
                embeddings.append([float(value) for value in vector])
        return SequenceScoringResult(
            scores=scores, embeddings=embeddings, model=self.version,
            confidence=Confidence(
                band=ConfidenceBand.MEDIUM,
                basis="Evo 2 mean sequence log-likelihood; not a calibrated probability",
            ),
        )

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        del request
        raise NotImplementedError(
            "Evo 2 variant scoring requires normalized reference/alternate sequence contexts; "
            "coordinate-only CellXP requests are insufficient"
        )

    def predict_tracks(self, request: TrackPredictionRequest) -> TrackPredictionResult:
        del request
        raise NotImplementedError(
            "Evo 2 track prediction requires sequence input; a coordinate-only interval is insufficient"
        )


def create_alphagenome_backend(manifest: WorkerManifest) -> AlphaGenomeSdkBackend:
    del manifest
    api_key = os.getenv("ALPHAGENOME_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ALPHAGENOME_API_KEY is required")
    from alphagenome.data import genome  # type: ignore[import-not-found]
    from alphagenome.models import dna_client, variant_scorers  # type: ignore[import-not-found]

    client = dna_client.create(
        api_key, timeout=float(os.getenv("ALPHAGENOME_CONNECT_TIMEOUT_SECONDS", "30"))
    )
    return AlphaGenomeSdkBackend(
        client, genome=genome, dna_client=dna_client, variant_scorers=variant_scorers
    )


def create_evo2_backend(manifest: WorkerManifest) -> Evo2SdkBackend:
    del manifest
    import torch  # type: ignore[import-not-found]
    from evo2 import Evo2  # type: ignore[import-not-found]

    weight_path = os.getenv("EVO2_WEIGHT_PATH", "/models/evo2_7b.pt")
    model = Evo2(
        "evo2_7b", local_path=weight_path,
        use_kernels=os.getenv("EVO2_USE_KERNELS", "0") == "1",
    )
    return Evo2SdkBackend(model, torch_module=torch)
