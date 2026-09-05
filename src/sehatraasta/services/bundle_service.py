from sehatraasta.domain import (
    CategoryReview,
    CostEntry,
    DiagnosticResult,
    ImagingItem,
    Instruction,
    InvestigationOrder,
    MedicationItem,
    Patient,
    ReferralBundle,
)


class BundleService:
    def __init__(self, repository):
        self.repository = repository

    def create_patient(self, ID, name, birth_year, language):
        patient = Patient(ID, name, birth_year, language)
        self.repository.add_patient(patient)
        return patient

    def get_patient(self, patient_id):
        patient = self.repository.get_patient(patient_id)
        if patient is None:
            raise ValueError("patient not found")
        return patient

    def create_bundle(
        self,
        patient_id,
        bundle_id,
        creation_time,
        source_facility,
        destination,
        status,
    ):
        if any(bundle.ID == bundle_id for _, bundle in self.list_bundles()):
            raise ValueError("duplicate referral ID")

        patient = self.get_patient(patient_id)
        bundle = ReferralBundle(
            bundle_id,
            creation_time,
            source_facility,
            destination,
            status,
        )
        patient.add_referral(bundle)
        self.repository.save_patient(patient)
        return bundle

    def get_bundle_owner(self, bundle_id):
        for patient in self.repository.list_patients():
            for bundle in patient.referrals:
                if bundle.ID == bundle_id:
                    return patient, bundle
        raise ValueError("bundle not found")

    def get_bundle(self, bundle_id):
        _, bundle = self.get_bundle_owner(bundle_id)
        return bundle

    def list_bundles(self):
        bundles = []
        for patient in self.repository.list_patients():
            for bundle in patient.referrals:
                bundles.append((patient, bundle))
        return bundles

    def _save_bundle(self, patient):
        self.repository.save_patient(patient)

    def add_medication(
        self,
        bundle_id,
        ID,
        name,
        strength,
        dose,
        route,
        frequency,
        duration,
        instructions,
        source,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        item = MedicationItem(
            name,
            strength,
            dose,
            route,
            frequency,
            duration,
            instructions,
            source,
            ID,
        )
        bundle.add_medication(item)
        self._save_bundle(patient)
        return item

    def add_order(self, bundle_id, name, order_date, source, workflow_status):
        patient, bundle = self.get_bundle_owner(bundle_id)
        order = InvestigationOrder(name, order_date, source, workflow_status)
        bundle.add_investigation_order(order)
        self._save_bundle(patient)
        return order

    def add_result(
        self,
        bundle_id,
        ID,
        name,
        result_date,
        source,
        interpretation,
        order_name=None,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        order = None
        if order_name is not None:
            for candidate in bundle.investigation_orders:
                if candidate.name == order_name:
                    order = candidate
                    break
            if order is None:
                raise ValueError("investigation order not found")

        result = DiagnosticResult(
            name,
            result_date,
            source,
            ID,
            interpretation,
            order,
        )
        bundle.add_diagnostic_result(result)
        self._save_bundle(patient)
        return result

    def add_imaging(
        self,
        bundle_id,
        ID,
        modality,
        body_part,
        imaging_date,
        facility,
        report,
        attachment_id,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        item = ImagingItem(
            modality,
            body_part,
            imaging_date,
            facility,
            report,
            ID,
            attachment_id,
        )
        bundle.add_imaging_item(item)
        self._save_bundle(patient)
        return item

    def add_instruction(
        self,
        bundle_id,
        category,
        language,
        text,
        source,
        instruction_date,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        instruction = Instruction(
            category,
            language,
            text,
            source,
            instruction_date,
        )
        bundle.add_instruction(instruction)
        self._save_bundle(patient)
        return instruction

    def add_cost(
        self,
        bundle_id,
        ID,
        category,
        amount,
        cost_date,
        source,
        note="",
        source_type="reported",
        source_identifier=None,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        entry = CostEntry(ID, category, amount, cost_date, source, note, source_type, source_identifier)
        bundle.add_cost_entry(entry)
        self._save_bundle(patient)
        return entry

    def set_category_review(
        self,
        bundle_id,
        category,
        state,
        text,
        review_time,
        note,
    ):
        patient, bundle = self.get_bundle_owner(bundle_id)
        review = CategoryReview(category, state, text, review_time, note)

        for index, existing in enumerate(bundle.category_reviews):
            if existing.category == category:
                bundle.category_reviews[index] = review
                break
        else:
            bundle.add_category_review(review)

        self._save_bundle(patient)
        return review

    def add_attachment_record(self, bundle_id, attachment):
        patient, bundle = self.get_bundle_owner(bundle_id)
        bundle.add_attachment(attachment)
        self._save_bundle(patient)
        return attachment

    def list_cost_entries(self, bundle_id):
        bundle = self.get_bundle(bundle_id)
        return list(bundle.cost_entries)

    def total_cost_pkr(self, bundle_id):
        return self.get_bundle(bundle_id).total_cost_pkr()

    def update_bundle(self, bundle_id, source_facility, destination, status):
        patient, bundle = self.get_bundle_owner(bundle_id)
        bundle.source_facility = source_facility
        bundle.destination = destination
        bundle.status = status
        bundle.checks()
        self.repository.save_patient(patient)
        return bundle
