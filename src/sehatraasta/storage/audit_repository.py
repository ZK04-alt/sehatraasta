from .db import connect_database


class AuditRepository:
    """Only IDs, fixed actions and outcomes; never document text or filenames."""

    def __init__(self, path):
        self.path = path

    def record(self, connection, bundle_id, attachment_id, action, outcome):
        connection.execute(
            "INSERT INTO file_audit_events(bundle_id, attachment_id, action, outcome) VALUES (?, ?, ?, ?)",
            (bundle_id, attachment_id, action, outcome),
        )

    def list_events(self, bundle_id):
        connection = connect_database(self.path, read_only=True)
        try:
            return [dict(row) for row in connection.execute(
                "SELECT * FROM file_audit_events WHERE bundle_id = ? ORDER BY event_id", (bundle_id,))]
        finally:
            connection.close()
