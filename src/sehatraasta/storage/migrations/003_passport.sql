BEGIN TRANSACTION;
CREATE TABLE referral_context (
    bundle_id TEXT PRIMARY KEY NOT NULL,
    medical_history TEXT NOT NULL DEFAULT '',
    allergies TEXT NOT NULL DEFAULT '',
    referral_reason TEXT NOT NULL DEFAULT '',
    referral_notes TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    follow_up_date TEXT,
    source TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(bundle_id) REFERENCES referral_bundles(bundle_id) ON DELETE CASCADE
);
INSERT INTO schema_version(version) VALUES (3);
COMMIT;
