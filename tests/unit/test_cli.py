import json

from sehatraasta.cli import (
    EXIT_STORAGE_FAILURE,
    EXIT_SUCCESS,
    EXIT_VALIDATION_FAILURE,
    main,
)
from sehatraasta.services import SYNTHETIC_WARNING


def run_cli(path, arguments):
    return main(["--data-file", str(path), *arguments])


def create_demo_case(path):
    commands = [
        [
            "create-patient",
            "--id",
            "SR-DEMO-001",
            "--name",
            "Amina Demo",
            "--birth-year",
            "1980",
            "--language",
            "urdu",
        ],
        [
            "create-bundle",
            "--patient-id",
            "SR-DEMO-001",
            "--bundle-id",
            "RB-001",
            "--created",
            "2026-08-30T10:00:00",
            "--source",
            "Demo BHU",
            "--destination",
            "Demo District Hospital - Orthopaedics",
        ],
        [
            "add-medication",
            "--bundle-id",
            "RB-001",
            "--id",
            "MD-001",
            "--name",
            "Demo medicine",
            "--strength",
            "10 mg",
            "--dose",
            "one tablet",
            "--route",
            "oral",
            "--frequency",
            "once daily",
            "--duration",
            "five days",
            "--instructions",
            "Take after a fictional meal.",
            "--source",
            "synthetic referral note",
        ],
        [
            "add-order",
            "--bundle-id",
            "RB-001",
            "--name",
            "X-ray",
            "--date",
            "2026-08-30",
            "--source",
            "Demo BHU",
            "--status",
            "ordered",
        ],
        [
            "add-result",
            "--bundle-id",
            "RB-001",
            "--id",
            "DR-001",
            "--name",
            "X-ray result",
            "--date",
            "2026-08-30",
            "--source",
            "Demo District Hospital",
            "--interpretation",
            "Pending",
            "--order-name",
            "X-ray",
        ],
        [
            "add-attachment",
            "--bundle-id",
            "RB-001",
            "--id",
            "AT-001",
            "--category",
            "imaging",
            "--name",
            "demo-xray.png",
            "--mime-type",
            "image/png",
            "--sha",
            "a" * 64,
            "--date",
            "2026-08-30",
            "--source",
            "synthetic attachment metadata",
            "--size",
            "1200",
        ],
        [
            "add-imaging",
            "--bundle-id",
            "RB-001",
            "--id",
            "IM-001",
            "--modality",
            "X-ray",
            "--body-part",
            "knee",
            "--date",
            "2026-08-30",
            "--facility",
            "Demo District Hospital",
            "--report",
            "Pending",
            "--attachment-id",
            "AT-001",
        ],
        [
            "add-instruction",
            "--bundle-id",
            "RB-001",
            "--category",
            "follow-up",
            "--language",
            "urdu",
            "--text",
            "Synthetic follow-up instruction",
            "--source",
            "synthetic referral note",
            "--date",
            "2026-08-30",
        ],
        [
            "add-cost",
            "--bundle-id",
            "RB-001",
            "--id",
            "CO-001",
            "--category",
            "travel",
            "--amount",
            "2500",
            "--date",
            "2026-08-30",
            "--source",
            "demo interview response",
        ],
        [
            "set-review",
            "--bundle-id",
            "RB-001",
            "--category",
            "medication list",
            "--state",
            "present",
            "--text",
            "Medication list reviewed",
            "--time",
            "2026-08-30T11:00:00",
            "--note",
            "synthetic review",
        ],
        [
            "set-review",
            "--bundle-id",
            "RB-001",
            "--category",
            "diagnostic results",
            "--state",
            "pending",
            "--text",
            "Result pending",
            "--time",
            "2026-08-30T11:00:00",
            "--note",
            "synthetic review",
        ],
        [
            "set-review",
            "--bundle-id",
            "RB-001",
            "--category",
            "imaging reports",
            "--state",
            "pending",
            "--text",
            "Imaging report pending",
            "--time",
            "2026-08-30T11:00:00",
            "--note",
            "synthetic review",
        ],
    ]

    for command in commands:
        assert run_cli(path, command) == EXIT_SUCCESS


def test_scripted_demo_case_display(tmp_path, capsys):
    path = tmp_path / "development.json"
    create_demo_case(path)
    capsys.readouterr()

    assert run_cli(path, ["show-bundle", "--bundle-id", "RB-001"]) == EXIT_SUCCESS

    output = capsys.readouterr().out
    assert SYNTHETIC_WARNING in output
    assert "Destination: Demo District Hospital - Orthopaedics" in output
    assert "Present:\n  - medication list" in output
    assert "Pending:\n  - diagnostic results\n  - imaging reports" in output
    assert "Not reviewed:" in output
    assert "Missing:\n  (none)" in output
    assert "Demo medicine" in output
    assert "X-ray: ordered" in output
    assert "travel: PKR 2,500.00 | source: demo interview response" in output
    assert "Total: PKR 2,500.00" in output


def test_cli_lists_costs_bundles_and_exports_bundle(tmp_path, capsys):
    path = tmp_path / "development.json"
    create_demo_case(path)
    capsys.readouterr()

    assert run_cli(path, ["list-bundles"]) == EXIT_SUCCESS
    assert "RB-001 | patient: SR-DEMO-001" in capsys.readouterr().out

    assert run_cli(path, ["list-costs", "--bundle-id", "RB-001"]) == EXIT_SUCCESS
    costs = capsys.readouterr().out
    assert "CO-001 | travel | PKR 2,500.00" in costs
    assert "Total: PKR 2,500.00" in costs

    output = tmp_path / "exports" / "bundle.json"
    assert run_cli(
        path,
        ["export-bundle", "--bundle-id", "RB-001", "--output", str(output)],
    ) == EXIT_SUCCESS
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["warning"] == SYNTHETIC_WARNING
    assert document["total_cost_pkr"] == "2500"


def test_cli_returns_validation_exit_code_for_invalid_costs(tmp_path, capsys):
    path = tmp_path / "development.json"
    create_demo_case(path)
    capsys.readouterr()

    common = [
        "add-cost",
        "--bundle-id",
        "RB-001",
        "--id",
        "CO-002",
        "--date",
        "2026-08-30",
    ]
    assert run_cli(
        path,
        [
            *common,
            "--category",
            "travel",
            "--amount",
            "-1",
            "--source",
            "demo source",
        ],
    ) == EXIT_VALIDATION_FAILURE
    assert run_cli(
        path,
        [
            *common,
            "--category",
            "travel",
            "--amount",
            "NaN",
            "--source",
            "demo source",
        ],
    ) == EXIT_VALIDATION_FAILURE
    assert run_cli(
        path,
        [
            *common,
            "--category",
            "travel",
            "--amount",
            "10",
            "--source",
            "",
        ],
    ) == EXIT_VALIDATION_FAILURE
    assert run_cli(
        path,
        [
            *common,
            "--category",
            "food",
            "--amount",
            "10",
            "--source",
            "demo source",
        ],
    ) == EXIT_VALIDATION_FAILURE


def test_cli_returns_storage_exit_code_without_overwriting_corrupt_file(
    tmp_path,
    capsys,
):
    path = tmp_path / "development.json"
    path.write_text("corrupt development data", encoding="utf-8")

    result = run_cli(path, ["list-bundles"])

    assert result == EXIT_STORAGE_FAILURE
    assert "Storage error:" in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == "corrupt development data"
