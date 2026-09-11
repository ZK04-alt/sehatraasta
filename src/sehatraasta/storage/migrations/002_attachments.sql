BEGIN TRANSACTION;

CREATE UNIQUE INDEX attachment_bundle_key ON attachments(attachment_id, bundle_id);
CREATE UNIQUE INDEX order_bundle_key ON investigation_orders(order_id, bundle_id);
CREATE UNIQUE INDEX instruction_bundle_key ON instructions(instruction_id, bundle_id);
CREATE UNIQUE INDEX result_bundle_key ON diagnostic_results(result_id, bundle_id);
CREATE UNIQUE INDEX imaging_bundle_key ON imaging_items(imaging_id, bundle_id);

CREATE TABLE managed_attachments (
    attachment_id TEXT PRIMARY KEY NOT NULL,
    bundle_id TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('document', 'reported', 'not supplied')),
    source_identifier TEXT,
    order_id INTEGER,
    result_id TEXT,
    imaging_id TEXT,
    instruction_id INTEGER,
    medication_list INTEGER NOT NULL DEFAULT 0 CHECK(medication_list IN (0, 1)),
    CHECK ((order_id IS NOT NULL) + (result_id IS NOT NULL) + (imaging_id IS NOT NULL)
           + (instruction_id IS NOT NULL) + medication_list <= 1),
    FOREIGN KEY(attachment_id, bundle_id) REFERENCES attachments(attachment_id, bundle_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(order_id, bundle_id) REFERENCES investigation_orders(order_id, bundle_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(result_id, bundle_id) REFERENCES diagnostic_results(result_id, bundle_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(imaging_id, bundle_id) REFERENCES imaging_items(imaging_id, bundle_id)
        DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY(instruction_id, bundle_id) REFERENCES instructions(instruction_id, bundle_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE file_audit_events (
    event_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    attachment_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    action TEXT NOT NULL CHECK(action IN ('import', 'retrieve', 'delete', 'reconcile')),
    outcome TEXT NOT NULL CHECK(outcome IN ('success', 'missing', 'integrity failure')),
    FOREIGN KEY(bundle_id) REFERENCES referral_bundles(bundle_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE bundle_tokens (
    bundle_id TEXT PRIMARY KEY NOT NULL,
    token TEXT NOT NULL UNIQUE,
    FOREIGN KEY(bundle_id) REFERENCES referral_bundles(bundle_id)
        DEFERRABLE INITIALLY DEFERRED
);

INSERT INTO schema_version(version) VALUES (2);
COMMIT;
