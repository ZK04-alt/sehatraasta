BEGIN TRANSACTION;
CREATE TABLE visit_drafts (
    draft_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);
CREATE TABLE visit_draft_fields (
    draft_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    value TEXT NOT NULL,
    PRIMARY KEY(draft_id, field_name, position),
    FOREIGN KEY(draft_id) REFERENCES visit_drafts(draft_id) ON DELETE CASCADE
);
INSERT INTO schema_version(version) VALUES (4);
COMMIT;
