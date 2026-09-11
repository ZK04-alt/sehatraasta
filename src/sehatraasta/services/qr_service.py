"""Checksums detect accidental alteration, not a forger or unauthorized access."""
import hashlib
import hmac
import json
import re
from uuid import uuid4

from sehatraasta.storage.db import connect_database


def make_payload(token):
    if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("invalid bundle token")
    check = hashlib.sha256(("1:" + token).encode("ascii")).hexdigest()[:16]
    return json.dumps({"id": token, "v": 1, "check": check}, separators=(",", ":"))


def verify_payload(payload):
    try:
        if not isinstance(payload, str) or len(payload) > 200:
            raise ValueError()
        data = json.loads(payload)
        if set(data) != {"id", "v", "check"} or type(data["v"]) is not int or data["v"] != 1:
            raise ValueError()
        expected = json.loads(make_payload(data["id"]))
        if not isinstance(data["check"], str) or not hmac.compare_digest(data["check"], expected["check"]):
            raise ValueError()
        return data["id"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("invalid or altered QR payload") from None


class QRService:
    def __init__(self, database):
        self.database = database

    def for_bundle(self, bundle_id):
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM referral_bundles WHERE bundle_id = ?", (bundle_id,)).fetchone() is None:
                    raise ValueError("bundle not found")
                row = connection.execute("SELECT token FROM bundle_tokens WHERE bundle_id = ?", (bundle_id,)).fetchone()
                token = row[0] if row else uuid4().hex
                if row is None:
                    connection.execute("INSERT INTO bundle_tokens VALUES (?, ?)", (bundle_id, token))
            return make_payload(token)
        finally:
            connection.close()

    def lookup(self, payload):
        token = verify_payload(payload)
        connection = connect_database(self.database, read_only=True)
        try:
            row = connection.execute("SELECT bundle_id FROM bundle_tokens WHERE token = ?", (token,)).fetchone()
            if row is None:
                raise ValueError("bundle not found on this device")
            return row[0]
        finally:
            connection.close()

    def lookup_short(self, short_id):
        if not isinstance(short_id, str) or not re.fullmatch(r"[a-f0-9]{12}", short_id):
            raise ValueError("invalid short lookup ID")
        connection = connect_database(self.database, read_only=True)
        try:
            matches = connection.execute("SELECT bundle_id FROM bundle_tokens WHERE substr(token, 1, 12) = ?", (short_id,)).fetchall()
            if len(matches) != 1:
                raise ValueError("short ID missing or ambiguous; use the full QR payload")
            return matches[0][0]
        finally:
            connection.close()
