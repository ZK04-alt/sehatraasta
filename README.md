# SehatRaasta

SehatRaasta organizes a family's patients, visits and original documents locally in English, Urdu and Pashto. Save a paper first, then add historical medicines, tests, instructions and costs when useful. Patient name and one supported original are enough for a new paper; birth year, facility and medical date are optional. Dates can be exact, approximate or unknown. Printable summaries, local QR lookup, visit passports and whole-dataset backups remain available.

## Run on a computer

Python 3.12 or later is required. In Git Bash on Windows:

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
PYTHONPATH=src python -m sehatraasta.web
```

Open http://127.0.0.1:5000. Records are stored in `instance/sehatraasta.sqlite`; documents are stored beside it. Keep the whole instance folder when moving the application.

## Android

The Android application runs the same referral software on the phone, offline. See [Android installation and build instructions](android/README.md).

## Correct or remove records

Patient, visit, document and structured-record screens support correction and reassignment. Replacing a scan keeps the old original in **Removed items**. Ordinary removal hides records from active lists while retaining them locally for restore. Open **Menu → Removed items** to restore, or deliberately delete permanently after a separate confirmation. Failed byte cleanup remains visible for retry. Separate backups, exports, restored copies and printouts are outside this deletion. Confirmations become invalid if records change.

Typed unfinished work can resume after interruption; an unsaved selected file must be selected again. Search uses patient, facility, supplied medical date and original filename. Doctor reports let you choose visits and individual originals; historical medication entries do not claim to be a reconciled current medication list.

## Records and privacy

Records remain on the device running the app. There are no cloud accounts, automatic synchronization or analytics. There is no application-level encryption or user-account access control; exported files and backups are also unencrypted. Protect device access and stored copies. Files are checked for supported type and size; these checks are not malware screening.

SehatRaasta organizes information as entered. It does not diagnose, interpret results, recommend treatment or determine medical urgency. Verify source documents and review states.

## Verification


```bash
python -m pytest -q
```

Tests use isolated temporary datasets. `learning-labs/` and the phase documents contain historical learning exercises and do not describe the current application interface.
