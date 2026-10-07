BEGIN TRANSACTION;
CREATE TABLE removed_items (
    item_id TEXT PRIMARY KEY NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('patient','visit','document','record','replacement')),
    label TEXT NOT NULL,
    parent_patient TEXT,
    parent_visit TEXT,
    removed_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'removed' CHECK(state IN ('removed','purging')),
    snapshot TEXT NOT NULL
);
INSERT INTO schema_version(version) VALUES (6);
COMMIT;
