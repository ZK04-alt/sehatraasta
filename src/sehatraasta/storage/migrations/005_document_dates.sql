BEGIN TRANSACTION;

-- Rebuild only to relax nullability. The migration runner temporarily disables
-- FK actions before BEGIN, then verifies every relationship before committing.
CREATE TABLE patients_optional (
    patient_id TEXT PRIMARY KEY NOT NULL,
    display_name TEXT NOT NULL,
    birth_year INTEGER CHECK (birth_year IS NULL OR (typeof(birth_year) = 'integer' AND birth_year > 0)),
    revision INTEGER NOT NULL DEFAULT 0,
    language TEXT NOT NULL CHECK (language IN ('ENGLISH', 'URDU', 'PASHTO'))
);
INSERT INTO patients_optional SELECT * FROM patients;
DROP TABLE patients;
ALTER TABLE patients_optional RENAME TO patients;

DROP TRIGGER imaging_items_same_bundle_insert;
DROP TRIGGER imaging_items_same_bundle_update;
CREATE TABLE attachments_optional (
    attachment_id TEXT PRIMARY KEY NOT NULL,
    bundle_id TEXT NOT NULL,
    category TEXT NOT NULL,
    original_display_name TEXT NOT NULL,
    generated_stored_name TEXT NOT NULL DEFAULT '',
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (typeof(size_bytes) = 'integer' AND size_bytes > 0),
    sha256 TEXT NOT NULL,
    date TEXT,
    source TEXT NOT NULL,
    FOREIGN KEY (bundle_id) REFERENCES referral_bundles (bundle_id) ON DELETE CASCADE
);
INSERT INTO attachments_optional SELECT * FROM attachments;
DROP TABLE attachments;
ALTER TABLE attachments_optional RENAME TO attachments;
CREATE UNIQUE INDEX attachment_bundle_key ON attachments(attachment_id, bundle_id);
CREATE TRIGGER imaging_items_same_bundle_insert
BEFORE INSERT ON imaging_items
WHEN NEW.attachment_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM attachments
    WHERE attachment_id = NEW.attachment_id AND bundle_id != NEW.bundle_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked record belongs to another bundle');
END;
CREATE TRIGGER imaging_items_same_bundle_update
BEFORE UPDATE ON imaging_items
WHEN NEW.attachment_id IS NOT NULL AND EXISTS (
    SELECT 1 FROM attachments
    WHERE attachment_id = NEW.attachment_id AND bundle_id != NEW.bundle_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked record belongs to another bundle');
END;
CREATE TRIGGER attachments_keep_bundle
BEFORE UPDATE OF bundle_id ON attachments
WHEN EXISTS (
    SELECT 1 FROM imaging_items
    WHERE attachment_id = OLD.attachment_id AND bundle_id != NEW.bundle_id
)
BEGIN
    SELECT RAISE(ABORT, 'linked record belongs to another bundle');
END;

-- All historical creation_time values remain untouched and are NOT interpreted
-- as clinical dates. Existing visits honestly start with an unknown date.
ALTER TABLE referral_bundles ADD COLUMN medical_date_kind TEXT NOT NULL DEFAULT 'unknown'
    CHECK (medical_date_kind IN ('unknown', 'exact', 'approximate'));
ALTER TABLE referral_bundles ADD COLUMN medical_date_value TEXT
    CHECK ((medical_date_kind = 'unknown' AND medical_date_value IS NULL)
        OR (medical_date_kind IN ('exact', 'approximate') AND medical_date_value IS NOT NULL));

INSERT INTO schema_version(version) VALUES (5);
COMMIT;
