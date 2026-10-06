"""Patient-scoped report selection. Preserve supplied text; infer no diagnoses."""
from .referral_context import ReferralContextService
from .file_service import FileService
from sehatraasta.storage.errors import StorageError


class ReportDocumentError(ValueError):
    """An owned selected original failed verification; no private text in logs."""
    def __init__(self, document):
        super().__init__('selected document unavailable')
        self.document_name = document.name


class ReportSelectionError(ValueError):
    """An owned original needs its parent visit selected; disclose no other owner."""
    def __init__(self, document):
        super().__init__('document not found in selected visits')
        self.document_name = document.name


def supplied(value):
    return value is not None and str(value).strip().lower() not in ('', 'source not supplied', 'not supplied')


class DoctorReportService:
    def __init__(self, bundle_service):
        self.bundles = bundle_service
        self.database = bundle_service.repository.path

    def collect(self, patient_id, visit_ids, include_documents=True, document_ids=None):
        patient = self.bundles.get_patient(patient_id)
        if not visit_ids and isinstance(document_ids, list) and len(document_ids) <= 30:
            # Document-first selection still needs a useful, owned-only recovery message.
            owned_documents = {item.ID: item for visit in patient.referrals for item in visit.attachments}
            for identifier in document_ids:
                if isinstance(identifier, str) and identifier in owned_documents:
                    raise ReportSelectionError(owned_documents[identifier])
        if not visit_ids or len(visit_ids) > 20 or len(set(visit_ids)) != len(visit_ids):
            raise ValueError('choose between one and twenty visits')
        owned = {visit.ID: visit for visit in patient.referrals}
        if any(identifier not in owned for identifier in visit_ids):
            raise ValueError('visit not found for this patient')
        visits = sorted((owned[identifier] for identifier in visit_ids), key=lambda item: (item.creation_time, item.ID))
        available = {item.ID: item for visit in visits for item in visit.attachments}
        if document_ids is not None:
            if (not isinstance(document_ids, list) or len(document_ids) > 30
                    or any(not isinstance(identifier, str) for identifier in document_ids)
                    or len(set(document_ids)) != len(document_ids)):
                raise ValueError('choose up to thirty different documents')
            if any(identifier not in available for identifier in document_ids):
                owned_documents = {item.ID: item for visit in patient.referrals for item in visit.attachments}
                for identifier in document_ids:
                    if identifier not in available and identifier in owned_documents:
                        raise ReportSelectionError(owned_documents[identifier])
                raise ValueError('document not found in selected visits')
            selected = set(document_ids)
        else:
            selected = set(available) if include_documents else set()
        if len(selected) > 30:
            raise ValueError('choose fewer documents or visits')
        result = []
        for visit in visits:
            context = ReferralContextService(self.database).get(visit.ID)
            documents = []
            for item in visit.attachments:
                if item.ID in selected:
                    # Check existence and hash before promising a complete report.
                    try:
                        FileService(self.database).retrieve(item.ID)
                    except (ValueError, StorageError):
                        raise ReportDocumentError(item) from None
                    documents.append(item)
            context_fields = ('medical_history', 'allergies', 'referral_reason', 'referral_notes', 'department', 'follow_up_date', 'source')
            result.append(dict(bundle=visit, context={key: context[key] for key in context_fields if supplied(context.get(key))}, documents=documents))
        return patient, result
