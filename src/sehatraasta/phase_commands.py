"""CLI presentation only. Validation and persistence live in services."""
from datetime import date

from sehatraasta.domain import AttachmentCategory, Provenance, ProvenanceType
from sehatraasta.services.dataset_backup import DatasetBackupService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.print_service import PrintService
from sehatraasta.services.qr_service import QRService


def add_commands(commands):
    intake = commands.add_parser("import-file", help="Copy a validated synthetic attachment.")
    for name in ("bundle-id", "id", "file", "category", "date"):
        intake.add_argument("--" + name, required=True)
    intake.add_argument("--synthetic", action="store_true", help="Confirm fictional, non-clinical content only.")
    intake.add_argument("--source-type", choices=[item.value for item in ProvenanceType], default="not supplied")
    intake.add_argument("--source")
    intake.add_argument("--source-identifier")
    link = intake.add_mutually_exclusive_group()
    link.add_argument("--order-id", type=int)
    link.add_argument("--result-id")
    link.add_argument("--imaging-id")
    link.add_argument("--instruction-id", type=int)
    link.add_argument("--medication-list", action="store_true")
    download = commands.add_parser("download-file")
    download.add_argument("--id", required=True)
    download.add_argument("--output", required=True)
    delete = commands.add_parser("delete-file")
    delete.add_argument("--id", required=True)
    commands.add_parser("reconcile-files", help="Run only when no other process uses the instance.")
    for command in ("list-files", "file-audit", "link-targets"):
        child = commands.add_parser(command)
        child.add_argument("--bundle-id", required=True)
    printer = commands.add_parser("print-bundle")
    printer.add_argument("--bundle-id", required=True)
    printer.add_argument("--output", required=True)
    lookup = commands.add_parser("lookup-qr")
    lookup.add_argument("--payload", required=True)
    short = commands.add_parser("lookup-short-id")
    short.add_argument("--id", required=True)
    backup = commands.add_parser("backup-dataset")
    backup.add_argument("--output-folder", required=True)
    restore = commands.add_parser("restore-dataset")
    restore.add_argument("--archive", required=True)
    restore.add_argument("--destination")
    restore.add_argument("--confirm", action="store_true")


def restore_command(args):
    backup = DatasetBackupService(args.data_file)
    summary = backup.dry_run(args.archive)
    print("Validated synthetic backup:", summary)
    if args.confirm:
        if not args.destination:
            raise ValueError("choose a new destination folder")
        backup.restore(args.archive, args.destination, confirmed=True)
        print("Restored into the new folder; current data was not changed")
    else:
        print("Dry run only. Review this summary, then use --confirm and --destination.")


def run_command(args, bundles):
    files = FileService(args.data_file)
    if args.command == "import-file":
        try:
            category = AttachmentCategory(args.category.lower().replace("_", " "))
        except ValueError:
            raise ValueError("unsupported attachment category") from None
        files.import_file(args.bundle_id, args.id, args.file, category, date.fromisoformat(args.date),
                          Provenance(ProvenanceType(args.source_type), args.source, args.source_identifier),
                          args.synthetic, args.order_id, args.result_id, args.imaging_id,
                          args.instruction_id, args.medication_list)
        print("Stored synthetic attachment", args.id)
    elif args.command == "download-file":
        files.download(args.id, args.output)
        print("Downloaded attachment", args.id)
    elif args.command == "delete-file":
        outcome = files.delete(args.id)
        print("Deleted attachment record", args.id, "(file was missing)" if outcome == "missing" else "")
    elif args.command == "reconcile-files":
        print("Removed unreferenced generated files:", files.reconcile())
    elif args.command == "print-bundle":
        PrintService(bundles).export(args.bundle_id, args.output)
        print("Created offline printable summary")
        print("Print on A4 at 100% scale. Turn browser headers and footers OFF to avoid printing a local file address.")
    elif args.command == "lookup-qr":
        print("Bundle:", QRService(args.data_file).lookup(args.payload))
    elif args.command == "lookup-short-id":
        print("Bundle:", QRService(args.data_file).lookup_short(args.id))
    elif args.command == "backup-dataset":
        print("Created synthetic backup:", DatasetBackupService(args.data_file).create(args.output_folder))
    elif args.command == "file-audit":
        for row in files.audit.list_events(args.bundle_id):
            print(row["attachment_id"], row["occurred_at"], row["action"], row["outcome"])
    elif args.command == "list-files":
        for item in bundles.get_bundle(args.bundle_id).attachments:
            print(item.ID, item.category, "source:", item.source)
    elif args.command == "link-targets":
        bundle = bundles.get_bundle(args.bundle_id)
        for item in bundle.investigation_orders:
            print("order", item._storage_id, item.name)
        for item in bundle.instructions:
            print("instruction", item._storage_id, item.category)
        for item in bundle.diagnostic_results:
            print("result", item.ID, item.name)
        for item in bundle.imaging_items:
            print("imaging", item.ID, item.modality)
        print("medication list: use --medication-list")
    else:
        return False
    return True
