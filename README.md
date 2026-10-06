# SehatRaasta

SehatRaasta organizes patients, referral bundles, supporting documents, review states and reported costs. It works locally in English, Urdu and Pashto, with printable summaries, QR lookup, exports and backups.

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

## Remove a patient

Open **Patients**, select the patient, then **Remove patient**. Confirm to remove that patient, every associated bundle and their stored attachments. Other patients are preserved. Separate backups, exports, restored copies and printouts are not deleted. A confirmation becomes invalid if the records change before removal.

## Records and privacy

Records remain on the device running the app. There are no cloud accounts, automatic synchronization or analytics. There is no application-level encryption or user-account access control; exported files and backups are also unencrypted. Protect device access and stored copies. Files are checked for supported type and size; these checks are not malware screening.

SehatRaasta organizes information as entered. It does not diagnose, interpret results, recommend treatment or determine medical urgency. Verify source documents and review states.

## Verification

```bash
python -m pytest -q
```

Tests use isolated temporary datasets. `learning-labs/` and the phase documents contain historical learning exercises and do not describe the current application interface.
