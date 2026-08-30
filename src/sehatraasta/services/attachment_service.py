from sehatraasta.domain import Attachment


class AttachmentService:
    def __init__(self, bundle_service):
        self.bundle_service = bundle_service

    def add_metadata(
        self,
        bundle_id,
        ID,
        category,
        name,
        MIME_type,
        sha,
        attachment_date,
        source,
        size,
    ):
        attachment = Attachment(
            ID,
            category,
            name,
            MIME_type,
            sha,
            attachment_date,
            source,
            size,
        )
        return self.bundle_service.add_attachment_record(bundle_id, attachment)
