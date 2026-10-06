"""Patient-scoped report selection. Preserve supplied text; infer no diagnoses."""
from .referral_context import ReferralContextService
from .file_service import FileService


def supplied(value):
    return value is not None and str(value).strip().lower() not in ('', 'source not supplied', 'not supplied')


class DoctorReportService:
    def __init__(self, bundle_service):
        self.bundles = bundle_service
        self.database = bundle_service.repository.path

    def collect(self, patient_id, visit_ids, include_documents=True):
        patient = self.bundles.get_patient(patient_id)
        if not visit_ids or len(visit_ids) > 20 or len(set(visit_ids)) != len(visit_ids):
            raise ValueError('choose between one and twenty visits')
        owned = {visit.ID: visit for visit in patient.referrals}
        if any(identifier not in owned for identifier in visit_ids):
            raise ValueError('visit not found for this patient')
        visits = sorted((owned[identifier] for identifier in visit_ids), key=lambda item: (item.creation_time, item.ID))
        if include_documents and sum(len(visit.attachments) for visit in visits) > 30:
            raise ValueError('choose fewer documents or visits')
        result = []
        for visit in visits:
            context = ReferralContextService(self.database).get(visit.ID)
            documents = []
            if include_documents:
                for item in visit.attachments:
                    # Check existence and hash before promising a complete report.
                    FileService(self.database).retrieve(item.ID)
                    documents.append(item)
            context_fields = ('medical_history', 'allergies', 'referral_reason', 'referral_notes', 'department', 'follow_up_date', 'source')
            result.append(dict(bundle=visit, context={key: context[key] for key in context_fields if supplied(context.get(key))}, documents=documents))
        return patient, result
