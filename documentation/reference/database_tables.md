# Database Tables

Reference for the relational tables backing CellXP. The **authoritative schema, columns,
keys, and conventions** are defined in the spec — this page is a pointer until the tables are
generated/documented from the implemented models.

- Schema spec (source of truth): `specs/data/relational_schema.md`
- Provenance & reproducibility model: `specs/data/provenance_model.md`
- Object storage (large payloads): `specs/data/object_storage.md`
- Vector index (RAG): `specs/data/vector_index.md`
- Audit log: `specs/data/audit_log.md`
- ER diagram: `documentation/diagrams/database_schema.mmd`

Tables (overview): `users`, `sessions`, `runs`, `messages`, `subtasks`, `steps`, `evidence_items`,
`artifacts` (+ `artifact_evidence`), `clarifications`, `review_items`, `run_errors`, `macros`,
`audit_log`. See the schema spec for full definitions.
