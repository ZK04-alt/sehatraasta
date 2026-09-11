import argparse
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys
import sqlite3

from sehatraasta.domain import (
    CostCategory,
    InvestigationOrderStatus,
    Language,
    PresenceState,
    ReferralStatus,
    ReviewCategory,
)
from sehatraasta.services import (
    AttachmentService,
    BundleService,
    CompletenessService,
    ExportService,
    SYNTHETIC_WARNING,
)
from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.services.database_service import DatabaseService
from sehatraasta.phase_commands import add_commands, run_command, restore_command
from sehatraasta.storage.errors import log_storage_error


EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILURE = 2
EXIT_STORAGE_FAILURE = 3
DEFAULT_DATA_FILE = Path("instance") / "sehatraasta.sqlite"


def _add_argument(parser, name, help_text):
    parser.add_argument(name, required=True, help=help_text)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="sehatraasta",
        description="Synthetic referral-bundle development CLI.",
        epilog=(
            "Examples: sehatraasta create-patient --id SR-DEMO-001 "
            "--name 'Amina Demo' --birth-year 1980 --language urdu; "
            "sehatraasta list-bundles"
        ),
    )
    parser.add_argument(
        "--data-file", "--database",
        default=str(DEFAULT_DATA_FILE),
        help="Path to the synthetic SQLite database (old JSON files are preserved).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    add_commands(commands)

    create_patient = commands.add_parser("create-patient")
    _add_argument(create_patient, "--id", "Fictional patient ID.")
    _add_argument(create_patient, "--name", "Fictional patient name.")
    _add_argument(create_patient, "--birth-year", "Fictional birth year.")
    _add_argument(create_patient, "--language", "english, urdu, or pashto.")

    create_bundle = commands.add_parser("create-bundle")
    _add_argument(create_bundle, "--patient-id", "Existing fictional patient ID.")
    _add_argument(create_bundle, "--bundle-id", "New referral-bundle ID.")
    _add_argument(create_bundle, "--created", "Creation time in ISO format.")
    _add_argument(create_bundle, "--source", "Source facility text.")
    _add_argument(create_bundle, "--destination", "Referral destination text.")
    create_bundle.add_argument("--status", default="draft")

    update_bundle = commands.add_parser("update-bundle")
    for name in ("--bundle-id", "--source", "--destination", "--status"):
        _add_argument(update_bundle, name, name[2:].replace("-", " "))
    commands.add_parser("init-db")
    backup = commands.add_parser("backup-db")
    _add_argument(backup, "--output", "New backup database path.")
    restore = commands.add_parser("restore-db")
    _add_argument(restore, "--backup", "Existing backup database path.")
    _add_argument(restore, "--output", "New restored database path; existing files are preserved.")

    medication = commands.add_parser("add-medication")
    for name in (
        "--bundle-id",
        "--id",
        "--name",
        "--strength",
        "--dose",
        "--route",
        "--frequency",
        "--duration",
        "--instructions",
    ):
        _add_argument(medication, name, name[2:].replace("-", " "))
    medication.add_argument("--source", default="source not supplied")

    order = commands.add_parser("add-order")
    _add_argument(order, "--bundle-id", "Referral-bundle ID.")
    _add_argument(order, "--name", "Ordered test name.")
    _add_argument(order, "--date", "Order date in YYYY-MM-DD format.")
    order.add_argument("--source", default="source not supplied")
    _add_argument(order, "--status", "ordered, completed, or cancelled.")

    result = commands.add_parser("add-result")
    _add_argument(result, "--bundle-id", "Referral-bundle ID.")
    _add_argument(result, "--id", "Result ID.")
    _add_argument(result, "--name", "Result name.")
    _add_argument(result, "--date", "Result date in YYYY-MM-DD format.")
    result.add_argument("--source", default="source not supplied")
    _add_argument(result, "--interpretation", "Verbatim fictional result text.")
    result.add_argument("--order-name")

    attachment = commands.add_parser("add-attachment")
    for name in (
        "--bundle-id",
        "--id",
        "--category",
        "--name",
        "--mime-type",
        "--sha",
        "--date",
        "--source",
        "--size",
    ):
        _add_argument(attachment, name, name[2:].replace("-", " "))

    imaging = commands.add_parser("add-imaging")
    for name in (
        "--bundle-id",
        "--id",
        "--modality",
        "--body-part",
        "--date",
        "--facility",
        "--report",
        "--attachment-id",
    ):
        _add_argument(imaging, name, name[2:].replace("-", " "))

    instruction = commands.add_parser("add-instruction")
    for name in (
        "--bundle-id",
        "--category",
        "--language",
        "--text",
        "--date",
    ):
        _add_argument(instruction, name, name[2:].replace("-", " "))
    instruction.add_argument("--source", default="source not supplied")

    cost = commands.add_parser("add-cost")
    for name in (
        "--bundle-id",
        "--id",
        "--category",
        "--amount",
        "--date",
        "--source",
    ):
        _add_argument(cost, name, name[2:].replace("-", " "))
    cost.add_argument("--note", default="")
    cost.add_argument("--source-type", default="reported")
    cost.add_argument("--source-identifier", help="Source reference; defaults to the supplied source text.")

    review = commands.add_parser("set-review")
    for name in (
        "--bundle-id",
        "--category",
        "--state",
        "--text",
        "--time",
        "--note",
    ):
        _add_argument(review, name, name[2:].replace("-", " "))

    list_costs = commands.add_parser("list-costs")
    _add_argument(list_costs, "--bundle-id", "Referral-bundle ID.")

    show_bundle = commands.add_parser("show-bundle")
    _add_argument(show_bundle, "--bundle-id", "Referral-bundle ID.")

    commands.add_parser("list-bundles")

    export_bundle = commands.add_parser("export-bundle")
    _add_argument(export_bundle, "--bundle-id", "Referral-bundle ID.")
    _add_argument(export_bundle, "--output", "Output JSON path.")

    return parser


def _enum_value(enum_class, text, error_message):
    normalized = text.strip().lower().replace("_", " ")
    for member in enum_class:
        names = {member.name.lower().replace("_", " "), str(member.value).lower()}
        if normalized in names:
            return member
    raise ValueError(error_message)


def _date_value(text):
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ValueError("invalid date") from error


def _datetime_value(text):
    try:
        return datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError("invalid time") from error


def _decimal_value(text):
    try:
        return Decimal(text)
    except InvalidOperation as error:
        raise ValueError("invalid amount") from error


def _format_pkr(amount):
    return f"PKR {amount:,.2f}"


def _print_categories(title, categories):
    print(f"{title}:")
    if not categories:
        print("  (none)")
    for category in categories:
        print(f"  - {category.value}")


def _show_bundle(patient, bundle, completeness, bundle_service):
    print(SYNTHETIC_WARNING)
    print(f"Patient: {patient.name} ({patient.ID})")
    print(f"Bundle: {bundle.ID}")
    print(f"Source: {bundle.source_facility}")
    print(f"Destination: {bundle.destination}")
    print(f"Referral status: {bundle.status.value}")
    print()
    _print_categories("Present", completeness["present"])
    _print_categories("Pending", completeness["pending"])
    _print_categories("Missing", completeness["missing"])
    _print_categories("Not reviewed", completeness["not_reviewed"])
    _print_categories("Not applicable", completeness["not_applicable"])
    print()
    print("Medication records:")
    if not bundle.medication_item:
        print("  (none)")
    for medication in bundle.medication_item:
        print(
            f"  - {medication.name}: {medication.instructions} "
            f"| source: {medication.source}"
        )
    print("Investigation orders:")
    if not bundle.investigation_orders:
        print("  (none)")
    for order in bundle.investigation_orders:
        print(f"  - {order.name}: {order.workflow_status.value}")
    print("Diagnostic results:")
    if not bundle.diagnostic_results:
        print("  (none)")
    for result in bundle.diagnostic_results:
        print(f"  - {result.name}: {result.interpretation}")
    print("Imaging records:")
    if not bundle.imaging_items:
        print("  (none)")
    for imaging in bundle.imaging_items:
        print(f"  - {imaging.modality} {imaging.body_part}: {imaging.report}")
    print("Costs:")
    costs = bundle_service.list_cost_entries(bundle.ID)
    if not costs:
        print("  (none)")
    for entry in costs:
        print(
            f"  - {entry.category.value}: {_format_pkr(entry.amount)} "
            f"| source: {entry.source}"
        )
    print(f"Total: {_format_pkr(bundle_service.total_cost_pkr(bundle.ID))}")


def _run_command(args, bundle_service, attachment_service, completeness, exporter):
    if args.command == "create-patient":
        patient = bundle_service.create_patient(
            args.id,
            args.name,
            int(args.birth_year),
            _enum_value(Language, args.language, "unknown language"),
        )
        print(f"Created fictional patient {patient.ID}")

    elif args.command == "create-bundle":
        bundle = bundle_service.create_bundle(
            args.patient_id,
            args.bundle_id,
            _datetime_value(args.created),
            args.source,
            args.destination,
            _enum_value(ReferralStatus, args.status, "unknown referral status"),
        )
        print(f"Created referral bundle {bundle.ID}")

    elif args.command == "add-medication":
        bundle_service.add_medication(
            args.bundle_id,
            args.id,
            args.name,
            args.strength,
            args.dose,
            args.route,
            args.frequency,
            args.duration,
            args.instructions,
            args.source,
        )
        print("Added medication record")

    elif args.command == "add-order":
        bundle_service.add_order(
            args.bundle_id,
            args.name,
            _date_value(args.date),
            args.source,
            _enum_value(
                InvestigationOrderStatus,
                args.status,
                "unknown investigation order status",
            ),
        )
        print("Added investigation order")

    elif args.command == "add-result":
        bundle_service.add_result(
            args.bundle_id,
            args.id,
            args.name,
            _date_value(args.date),
            args.source,
            args.interpretation,
            args.order_name,
        )
        print("Added diagnostic result")

    elif args.command == "add-attachment":
        attachment_service.add_metadata(
            args.bundle_id,
            args.id,
            args.category,
            args.name,
            args.mime_type,
            args.sha,
            _date_value(args.date),
            args.source,
            float(args.size),
        )
        print("Added attachment metadata")

    elif args.command == "add-imaging":
        bundle_service.add_imaging(
            args.bundle_id,
            args.id,
            args.modality,
            args.body_part,
            _date_value(args.date),
            args.facility,
            args.report,
            args.attachment_id,
        )
        print("Added imaging record")

    elif args.command == "add-instruction":
        bundle_service.add_instruction(
            args.bundle_id,
            args.category,
            _enum_value(Language, args.language, "unknown language"),
            args.text,
            args.source,
            _date_value(args.date),
        )
        print("Added instruction")

    elif args.command == "add-cost":
        bundle_service.add_cost(
            args.bundle_id,
            args.id,
            _enum_value(CostCategory, args.category, "unsupported cost category"),
            _decimal_value(args.amount),
            _date_value(args.date),
            args.source,
            args.note,
            args.source_type,
            args.source_identifier,
        )
        print("Added cost entry")

    elif args.command == "set-review":
        bundle_service.set_category_review(
            args.bundle_id,
            _enum_value(ReviewCategory, args.category, "unknown review category"),
            _enum_value(PresenceState, args.state, "unknown presence state"),
            args.text,
            _datetime_value(args.time),
            args.note,
        )
        print("Set category review")

    elif args.command == "list-costs":
        costs = bundle_service.list_cost_entries(args.bundle_id)
        for entry in costs:
            print(
                f"{entry.ID} | {entry.category.value} | "
                f"{_format_pkr(entry.amount)} | source: {entry.source}"
            )
        print(f"Total: {_format_pkr(bundle_service.total_cost_pkr(args.bundle_id))}")

    elif args.command == "show-bundle":
        patient, bundle = bundle_service.get_bundle_owner(args.bundle_id)
        groups = completeness.group_categories(bundle)
        _show_bundle(patient, bundle, groups, bundle_service)

    elif args.command == "list-bundles":
        for patient, bundle in bundle_service.list_bundles():
            print(
                f"{bundle.ID} | patient: {patient.ID} | "
                f"{bundle.source_facility} -> {bundle.destination}"
            )

    elif args.command == "export-bundle":
        output = exporter.export_bundle(args.bundle_id, args.output)
        print(f"Exported {output}")

    elif args.command == "update-bundle":
        bundle_service.update_bundle(
            args.bundle_id, args.source, args.destination,
            _enum_value(ReferralStatus, args.status, "unknown referral status"),
        )
        print("Updated referral bundle")


def main(argv=None):
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    try:
        if args.command == "restore-dataset":
            restore_command(args)
            return EXIT_SUCCESS
        maintenance = DatabaseService(args.data_file)
        if args.command == "restore-db":
            print(f"Restored {maintenance.restore(args.backup, args.output)}")
            return EXIT_SUCCESS
        if args.command == "backup-db":
            print(f"Backup created: {maintenance.backup(args.output)}")
            return EXIT_SUCCESS
        repository = SQLiteRepository(args.data_file)
        if args.command == "init-db":
            print("Database initialized")
            return EXIT_SUCCESS
        bundle_service = BundleService(repository)
        if run_command(args, bundle_service):
            return EXIT_SUCCESS
        attachment_service = AttachmentService(bundle_service)
        completeness = CompletenessService()
        exporter = ExportService(bundle_service)
        _run_command(
            args,
            bundle_service,
            attachment_service,
            completeness,
            exporter,
        )
        return EXIT_SUCCESS
    except StorageError as error:
        print(f"Storage error: {error}", file=sys.stderr)
        return EXIT_STORAGE_FAILURE
    except (OSError, sqlite3.Error) as error:
        log_storage_error(args.data_file, "cli_operation", error)
        print("Storage error: operation failed; no internal paths are displayed", file=sys.stderr)
        return EXIT_STORAGE_FAILURE
    except (TypeError, ValueError) as error:
        print(f"Validation error: {error}", file=sys.stderr)
        return EXIT_VALIDATION_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
