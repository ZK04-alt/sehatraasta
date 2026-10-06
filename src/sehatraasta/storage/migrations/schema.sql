BEGIN TRANSACTION;

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_version (version)
VALUES (1);

CREATE TABLE patients (
    patient_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    birth_year INTEGER NOT NULL CHECK (birth_year > 0),
    language TEXT NOT NULL
        CHECK (language IN ('ENGLISH', 'URDU', 'PASHTO'))
);

CREATE TABLE referral_bundles (
    bundle_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    creation_time TEXT NOT NULL,
    source_facility TEXT NOT NULL,
    destination TEXT NOT NULL,
    referral_status TEXT NOT NULL
        CHECK (
            referral_status IN ('DRAFT', 'READY_FOR_REVIEW', 'ARCHIVED')
        ),
    FOREIGN KEY (patient_id)
        REFERENCES patients (patient_id)
        ON DELETE CASCADE
);

CREATE TABLE audit_events (
    audit_event_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor_label TEXT NOT NULL,
    result TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE instructions (
    instruction_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    category TEXT NOT NULL,
    language TEXT NOT NULL
        CHECK (language IN ('ENGLISH', 'URDU', 'PASHTO')),
    verbatim_text TEXT NOT NULL,
    author_source TEXT NOT NULL,
    date TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE cost_entries (
    cost_entry_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (
            category IN (
                'TRAVEL',
                'MEDICATION',
                'INVESTIGATION',
                'IMAGING',
                'CONSULTATION',
                'ACCOMMODATION',
                'OTHER'
            )
        ),
    amount_paisa INTEGER NOT NULL CHECK (amount_paisa >= 0),
    date TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (length(trim(source_type)) > 0),
    source_identifier TEXT NOT NULL
        CHECK (length(trim(source_identifier)) > 0),
    reported_by_label TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE attachments (
    attachment_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    category TEXT NOT NULL,
    original_display_name TEXT NOT NULL,
    generated_stored_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    sha256 TEXT NOT NULL,
    date TEXT NOT NULL,
    source TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE imaging_items (
    imaging_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    attachment_id TEXT,
    modality TEXT NOT NULL,
    body_part TEXT NOT NULL,
    date TEXT NOT NULL,
    facility TEXT NOT NULL,
    report TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE,
    FOREIGN KEY (attachment_id)
        REFERENCES attachments (attachment_id)
        ON DELETE SET NULL
);

CREATE TABLE medication_items (
    medication_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    verbatim_name TEXT NOT NULL,
    strength TEXT NOT NULL,
    dose_text TEXT NOT NULL,
    route_text TEXT NOT NULL,
    frequency_text TEXT NOT NULL,
    duration_text TEXT NOT NULL,
    instructions TEXT NOT NULL,
    source TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE encounters (
    encounter_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    date TEXT NOT NULL,
    facility TEXT NOT NULL,
    clinician_display_text TEXT NOT NULL,
    source_note TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE category_reviews (
    review_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (
            category IN (
                'ENCOUNTERS',
                'MEDICATION_LIST',
                'INVESTIGATION_ORDERS',
                'DIAGNOSTIC_RESULTS',
                'IMAGING_REPORTS',
                'INSTRUCTIONS',
                'ATTACHMENTS',
                'COSTS'
            )
        ),
    presence_state TEXT NOT NULL
        CHECK (
            presence_state IN (
                'PRESENT',
                'MISSING',
                'PENDING',
                'NOT_APPLICABLE'
            )
        ),
    reviewer_text TEXT NOT NULL,
    reviewed_time TEXT NOT NULL,
    note TEXT NOT NULL,
    UNIQUE (bundle_id, category),
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE investigation_orders (
    order_id INTEGER PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    test_name TEXT NOT NULL,
    order_date TEXT NOT NULL,
    ordering_source TEXT NOT NULL,
    workflow_status TEXT NOT NULL
        CHECK (workflow_status IN ('ORDERED', 'COMPLETED', 'CANCELLED')),
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE
);

CREATE TABLE diagnostic_results (
    result_id TEXT PRIMARY KEY,
    bundle_id TEXT NOT NULL,
    investigation_order_id INTEGER,
    test_name TEXT NOT NULL,
    result_date TEXT NOT NULL,
    source_summary TEXT NOT NULL,
    interpretation_note TEXT NOT NULL,
    FOREIGN KEY (bundle_id)
        REFERENCES referral_bundles (bundle_id)
        ON DELETE CASCADE,
    FOREIGN KEY (investigation_order_id)
        REFERENCES investigation_orders (order_id)
        ON DELETE SET NULL
);

COMMIT;
