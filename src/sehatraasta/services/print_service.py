"""Self-contained, offline HTML with explicit A4 pages and an embedded QR."""
import base64
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import textwrap

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError
from .qr_service import QRService, verify_payload
from .qr_image import render_qr_png


WARNING = "Verify source documents and review status"


def wrapped(text):
    lines = []
    for line in str(text).splitlines() or [""]:
        lines.extend(textwrap.wrap(line, width=78, replace_whitespace=True) or [""])
    return lines


class PrintService:
    def __init__(self, bundle_service):
        self.bundles = bundle_service
        self.database = bundle_service.repository.path

    def render(self, bundle_id):
        patient, bundle = self.bundles.get_bundle_owner(bundle_id)
        payload = QRService(self.database).for_bundle(bundle_id)
        token = verify_payload(payload)
        image = base64.b64encode(render_qr_png(payload, box_size=8)).decode("ascii")
        connection = connect_database(self.database, read_only=True)
        try:
            links = [dict(row) for row in connection.execute("SELECT * FROM managed_attachments WHERE bundle_id = ?", (bundle_id,))]
        finally:
            connection.close()

        overview = []
        medical_date = ('Date not known' if bundle.medical_date_kind == 'unknown' else
                        bundle.medical_date_kind.title() + ' date: ' + bundle.medical_date_value)
        identity = f"Patient: {patient.name}" + (f" | Born: {patient.birth_year}" if patient.birth_year else '')
        for line in ("SehatRaasta - Referral summary", identity, medical_date,
                     "Saved on this device: " + bundle.creation_time.isoformat(timespec='minutes'),
                     "Saved time is not a medical date.",
                     f"Source: {bundle.source_facility}", f"Destination: {bundle.destination}",
                     f"Referral status: {bundle.status.value}", "", "CATEGORY / STATE / REVIEWED TIME"):
            overview.extend(wrapped(line))
        from sehatraasta.domain import ReviewCategory
        reviews = {review.category: review for review in bundle.category_reviews}
        for category in ReviewCategory:
            review = reviews.get(category)
            state = review.state.value if review else "not reviewed"
            time = review.time.isoformat(timespec="minutes") if review else "not reviewed"
            overview.extend(wrapped(f"{category.value}: {state} | {time}"))
        overview.extend(wrapped(f"Reported cost total: PKR {bundle.total_cost_pkr():,.2f}"))
        overview.extend(wrapped("Reported cost only; this is not a measure of economic impact."))
        overview.extend(wrapped("Source document IDs: " + (", ".join(item.ID for item in bundle.attachments) or "none supplied")))

        detail = ["COST ENTRIES (reported PKR)"]
        from .referral_context import ReferralContextService
        context = ReferralContextService(self.database).get(bundle_id)
        notes = ['HISTORY AND REFERRAL NOTES (as supplied)']
        for field in ('department', 'referral_reason', 'medical_history', 'allergies', 'referral_notes', 'follow_up_date', 'source'):
            notes.extend(wrapped(field.replace('_', ' ').title() + ': ' + (context[field] or 'not recorded')))
        notes.append('Blank allergies mean not recorded, not no known allergies.')
        detail = notes + [''] + detail
        if not bundle.cost_entries:
            detail.append("No cost entries supplied.")
        for item in bundle.cost_entries:
            detail.extend(wrapped(f"{item.ID} | {item.category.value} | {item.date} | PKR {item.amount:,.2f}"))
            detail.extend(wrapped(f"Source: {item.source} | {item.source_type} | {item.source_identifier}"))
        detail.extend(wrapped(f"EXACT TOTAL: PKR {bundle.total_cost_pkr():,.2f}"))

        def sources(column, value):
            ids = [row["attachment_id"] for row in links if row[column] == value]
            return ", ".join(ids) if ids else "source document not supplied"

        detail.extend(["", "MEDICATIONS - verbatim supplied text"])
        for item in bundle.medication_item:
            detail.extend(wrapped(f"{item.ID}: {item.name}; strength: {item.strength}; dose: {item.dose}; route: {item.route}; frequency: {item.frequency}; duration: {item.duration}"))
            detail.extend(wrapped(item.instructions))
            detail.extend(wrapped(f"Source: {item.source} | Document: {sources('medication_list', 1)}"))
        detail.extend(["", "INVESTIGATION ORDERS"])
        for item in bundle.investigation_orders:
            detail.extend(wrapped(f"Order {item._storage_id}: {item.name} | {item.date} | {item.workflow_status.value}"))
            detail.extend(wrapped(f"Source: {item.source} | Document: {sources('order_id', item._storage_id)}"))
        detail.extend(["", "DIAGNOSTIC RESULTS"])
        for item in bundle.diagnostic_results:
            detail.extend(wrapped(f"{item.ID}: {item.name} | {item.date} | {item.interpretation}"))
            detail.extend(wrapped(f"Source: {item.source} | Document: {sources('result_id', item.ID)}"))
        detail.extend(["", "IMAGING REPORTS"])
        for item in bundle.imaging_items:
            detail.extend(wrapped(f"{item.ID}: {item.modality} | {item.body_part} | {item.date} | {item.report}"))
            detail.extend(wrapped(f"Source: {item.facility} | Document: {item.Attachment_ID or sources('imaging_id', item.ID)}"))
        detail.extend(["", "INSTRUCTIONS - verbatim supplied text"])
        for item in bundle.instructions:
            detail.extend(wrapped(f"Instruction {item._storage_id}: {item.date} | {item.text}"))
            detail.extend(wrapped(f"Source: {item.source} | Document: {sources('instruction_id', item._storage_id)}"))
        detail.extend(["", "ATTACHMENT SOURCES (no document previews)"])
        for item in bundle.attachments:
            day = item.date.isoformat() if item.date else 'Date not known'
            detail.extend(wrapped(f"{item.ID} | {item.category} | {day} | Source: {item.source}"))
            for link in links:
                if link["attachment_id"] == item.ID:
                    detail.extend(wrapped(f"Provenance: {link['source_type']} | Reference: {link['source_identifier'] or 'source not supplied'}"))

        pages = [overview[:29]]
        remaining = overview[29:] + [""] + detail
        while remaining:
            pages.append(remaining[:44])
            remaining = remaining[44:]
        generated = datetime.now(timezone.utc).isoformat(timespec="minutes")
        html = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
                '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'">',
                '<title>SehatRaasta referral</title><style>',
                '@page { size: A4; margin: 12mm; } * { box-sizing: border-box; }',
                'body { margin:0; background:#eee; color:#000; }',
                '.page { width:186mm; height:270mm; padding:4mm; margin:8mm auto; background:white; position:relative; break-after:page; }',
                '.page:last-child { break-after:auto; } pre { margin:0; white-space:pre-wrap; overflow-wrap:anywhere; font:10pt/1.5 "Courier New",monospace; }',
                'footer { position:absolute; bottom:4mm; left:4mm; right:4mm; border-top:1px solid black; padding-top:2mm; font:9pt Arial,sans-serif; }',
                '.qr { width:30mm; height:30mm; } .lookup { font:9pt Arial,sans-serif; }',
                '@media print { body { background:white; } .page { margin:0; } nav,button { display:none; } }',
                '</style></head><body>']
        for index, lines in enumerate(pages):
            html.append('<section class="page"><pre>' + escape("\n".join(lines)) + '</pre>')
            if index == 0:
                html.append(f'<img class="qr" alt="Local bundle lookup QR" src="data:image/png;base64,{image}">')
                html.append('<div class="lookup">Short lookup ID: ' + token[:12] + '<br>Local lookup only; not authentication.</div>')
            html.append('<footer>' + escape(f"{WARNING} | Bundle {bundle.ID} | Page {index + 1}/{len(pages)}") + '<br>' + escape(f"Generated {generated}") + '</footer></section>')
        html.append('</body></html>')
        return "".join(html)

    def export(self, bundle_id, output):
        target = Path(output)
        if target.suffix.lower() != ".html" or target.resolve().is_relative_to(Path(self.database).parent.resolve()):
            raise ValueError("choose a new HTML file outside the instance folder")
        html = self.render(bundle_id)
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(html)
        except OSError:
            raise StorageError("could not write print summary; choose a new file") from None
