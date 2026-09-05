from pathlib import Path

from sehatraasta.storage.repositories import bundle_to_dict, write_json_safely

from .completeness_service import CompletenessService


SYNTHETIC_WARNING = (
    "SYNTHETIC DEVELOPMENT DATA ONLY. "
    "Do not use this file for medical care or clinical decisions."
)


class ExportService:
    def __init__(self, bundle_service):
        self.bundle_service = bundle_service
        self.completeness_service = CompletenessService()

    def export_bundle(self, bundle_id, output_path):
        target = Path(output_path).resolve()
        database = Path(self.bundle_service.repository.path).resolve()
        same_file = target.exists() and database.exists() and target.samefile(database)
        if same_file or target == database or database in (
            target.with_name(target.name + ".tmp"),
            target.with_name(target.name + ".bak"),
        ):
            raise ValueError("export path must be separate from the database")
        patient, bundle = self.bundle_service.get_bundle_owner(bundle_id)
        groups = self.completeness_service.group_categories(bundle)
        completeness = {
            name: [category.value for category in categories]
            for name, categories in groups.items()
        }
        payload = {
            "warning": SYNTHETIC_WARNING,
            "patient": {
                "ID": patient.ID,
                "name": patient.name,
                "birth_year": patient.birth_year,
                "language": patient.language.name,
            },
            "bundle": bundle_to_dict(bundle),
            "completeness": completeness,
            "total_cost_pkr": str(bundle.total_cost_pkr()),
        }
        return Path(write_json_safely(output_path, payload))
