"""Generate a public fictional print sample into a NEW chosen folder.

Run with PYTHONPATH=src python tests/manual/phase45_print_sample.py OUTPUT_FOLDER.
The automated test fixture creates all data; no real documents are read.
"""
from pathlib import Path
import runpy
import sys

from sehatraasta.services.print_service import PrintService


if __name__ == "__main__":
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=False)
    examples = runpy.run_path(str(Path(__file__).parents[1] / "integration" / "test_phase45.py"))
    case = examples["case"].__wrapped__(folder)
    examples["upload"](case, medication_list=True)
    database, bundles, files, source = case
    patient = bundles.get_patient("SR-DEMO-001")
    patient.referrals[0].instructions[0].text = "Long synthetic instruction for print wrapping. " * 40
    bundles.repository.save_patient(patient)
    PrintService(bundles).export("SR-DEMO-001", folder / "summary.html")
    print("Synthetic print sample created.")
