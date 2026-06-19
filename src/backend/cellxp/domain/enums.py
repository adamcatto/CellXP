"""Canonical domain enums for CellXP.

These vocabularies are part of the frozen domain contract (Wave 0). They name the
coordinate conventions, strands, and contig topologies that every positioned entity
in the system reasons about. See `documentation/explanation/coordinate_systems.md`.
"""

from __future__ import annotations

from enum import Enum


class Strand(str, Enum):
    """Strand of a positioned feature.

    `UNSTRANDED` (`.`) means strand is unknown or not meaningful for the feature;
    strand-aware operations must state how they use it (`coordinate_systems.md` §3).
    """

    PLUS = "+"
    MINUS = "-"
    UNSTRANDED = "."


class CoordinateSystem(str, Enum):
    """A coordinate convention an interval/position may be expressed in.

    `ZERO_BASED_HALF_OPEN` is the **internal canonical** representation used by every
    `GenomicInterval` (`coordinate_systems.md` §3). The others are edge formats that are
    converted to/from canonical via `domain/coordinates.py` — never compared ad hoc.
    """

    ZERO_BASED_HALF_OPEN = "0-based-half-open"  # BED-style; canonical internal
    ONE_BASED_INCLUSIVE = "1-based-inclusive"  # VCF / GFF / genome-browser display


class SequenceAlphabet(str, Enum):
    """The biological alphabet a sequence is written in (`input_normalizer.md` step 2)."""

    DNA = "dna"
    RNA = "rna"
    PROTEIN = "protein"


class SourceKind(str, Enum):
    """Kind of evidence backing a claim (`evidence_and_confidence.md` §2)."""

    MEASUREMENT = "measurement"  # experimental assay readout (highest prior)
    DATABASE = "database"  # GWAS Catalog, ClinVar, UniProt, GTEx record
    LITERATURE = "literature"  # cited paper/preprint passage (RAG)
    MODEL = "model"  # AlphaGenome/Evo2/ESMFold/Boltz prediction
    COMPUTATION = "computation"  # deterministic calc (GC content, coordinate mapping)


class ConfidenceBand(str, Enum):
    """Qualitative confidence band; always present (`evidence_and_confidence.md` §4)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ArtifactType(str, Enum):
    """Registered artifact types (`artifact_model.md` §4). A one-off blob is not valid."""

    GENOME_TRACK = "genome_track"
    LOCUS_PLOT = "locus_plot"
    CONTACT_MAP = "contact_map"
    MOTIF_LOGO = "motif_logo"
    STRUCTURE_3D = "structure_3d"
    GUIDE_TABLE = "guide_table"
    FEATURE_TABLE = "feature_table"
    FUNCTION_TABLE = "function_table"
    PROTEIN_DESIGN_TABLE = "protein_design_table"
    STAPLE_TABLE = "staple_table"
    ORIGAMI = "origami"
    ORIGAMI_SIMULATION = "origami_simulation"
    SEQUENCE_VIEWER = "sequence_viewer"
    COORDINATE_TABLE = "coordinate_table"
    OFF_TARGET_TABLE = "off_target_table"
    AFFINITY_PANEL = "affinity_panel"
    QC_PANEL = "qc_panel"
    REPORT = "report"
    FILE = "file"


class PlanKind(str, Enum):
    """Task-taxonomy plan kind (`task_patterns.md` §0, `state_schema.md` §6)."""

    ATOMIC = "atomic"
    MACRO = "macro"
    COMPOSED = "composed"


class SubtaskType(str, Enum):
    """Capability a subtask routes to (`routing_policy.md` §2, `state_schema.md` §6)."""

    VARIANT_EFFECT = "variant_effect"
    GWAS = "gwas"
    CRISPR = "crispr"
    ANNOTATION = "annotation"
    BINDING = "binding"
    STRUCTURE = "structure"
    ORIGAMI = "origami"
    RAG = "rag"
    VISUALIZATION = "visualization"


class TaskStatus(str, Enum):
    """Subtask/step lifecycle (`state_schema.md` §14)."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"
    NEEDS_REVIEW = "needs_review"


class ReviewGateStatus(str, Enum):
    """Human-review gate state (`state_schema.md` §12, `human_review_policy.md`)."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class ReviewDecision(str, Enum):
    """Per-item review decision (`state_schema.md` §12)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskDecision(str, Enum):
    """Early risk-gate outcome (`safety_model.md` §3, `risk_classifier.md`)."""

    ALLOW = "allow"  # ordinary research request; proceed normally
    RESTRICT = "restrict"  # legitimate but sensitive; force review gate + extra logging
    BLOCK = "block"  # primary purpose hazardous; refuse or escalate, no capability work


class VariantNotation(str, Enum):
    """Surface syntax a variant was written in (`input_normalizer.md` step 1)."""

    RSID = "rsid"  # dbSNP identifier, e.g. rs334
    VCF = "vcf"  # chrom/pos/ref/alt (1-based), space/colon/dash separated
    HGVS_GENOMIC = "hgvs_genomic"  # accession:g.POSref>alt substitution


class OrganismClass(str, Enum):
    """Organism class that drives oracle selection (`supported_species.md` §1)."""

    MAMMALIAN = "mammalian"
    VERTEBRATE_NONMAMMAL = "vertebrate_nonmammal"
    INVERTEBRATE = "invertebrate"
    PLANT = "plant"
    FUNGAL = "fungal"
    PROKARYOTE = "prokaryote"


class Topology(str, Enum):
    """Whether a contig/assembly replicon is linear or circular.

    Topology is a property of the assembly, resolved by the reference service
    (`services/reference/`); circular wrap (origin-crossing) intervals are only valid on
    `CIRCULAR` contigs (`coordinate_systems.md` §5/§6).
    """

    LINEAR = "linear"
    CIRCULAR = "circular"
