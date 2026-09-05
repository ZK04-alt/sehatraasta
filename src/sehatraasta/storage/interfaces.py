class PatientRepository:
    """The four operations BundleService needs from any storage implementation."""

    def add_patient(self, patient):
        raise NotImplementedError

    def get_patient(self, patient_id):
        raise NotImplementedError

    def list_patients(self):
        raise NotImplementedError

    def save_patient(self, patient):
        raise NotImplementedError
