# SehatRaasta Safety Rules

## Current development status

SehatRaasta is an educational prototype. It is not a medical device or a clinical record system.

> **WARNING — FICTIONAL DATA ONLY**
>
> Do not enter real patient information during development. Use only fictional cases and fictional documents.

## Product limits

- SehatRaasta does not diagnose a condition.
- SehatRaasta does not recommend treatment.
- SehatRaasta does not replace a doctor, hospital record, or emergency service.
- SehatRaasta organizes referral information and supporting documents.
- A qualified person must review medical information before clinical use.
- The project must not claim that a profile is complete or medically correct.

## Data rules for development

1. Use fictional names, dates, contact details, documents, and medical information.
2. Do not upload real prescriptions, test results, scans, identity documents, or referral letters.
3. Do not copy real patient information into screenshots, demonstrations, tests, or Git history.
4. Store local runtime data only in ignored folders such as `instance/` and `attachments/`.
5. Do not commit databases, attachments, secret keys, passwords, or `.env` files.
6. Remove metadata from demonstration files before publication.

## Information source labels

The app must identify the source of each important item:

- **Patient-entered:** The patient or caregiver supplied the information.
- **Clinician-entered:** A healthcare worker entered the information.
- **Clinician-reviewed:** A qualified healthcare worker reviewed the information.
- **Original document:** An attached source document supports the information.
- **Unverified:** No qualified reviewer confirmed the information.

The app must not present patient-entered or extracted information as clinician-confirmed information.

## Documents and automatic extraction

- Keep the original document with each extracted item when permitted.
- Treat image or OCR extraction as unverified draft information.
- Require a person to check medicine names, doses, dates, test values, and instructions.
- Do not use automatic extraction to make a diagnosis or treatment decision.

## Referral summary and QR rules

- Mark missing, pending, unverified, and not-applicable items clearly.
- Do not state that a referral profile is 100% complete.
- Do not place private medical information directly inside a QR code.
- A QR code may contain a non-sensitive reference or local identifier.
- Show the source and review status of important information.

## Interface notice

Show this notice when the CLI starts. Show the same notice in the future web interface:

> **DEVELOPMENT VERSION — Use fictional data only. Do not enter real patient or medical information.**

## Requirements before real-person research

Do not collect real patient data or begin a clinic pilot until all required safeguards exist.

Before real-person research begins:

1. Obtain written permission from the participating institution.
2. Obtain the required ethics or research review.
3. Confirm supervision by a qualified adult or professional.
4. Use an approved consent process.
5. Define who can access, correct, export, and delete the data.
6. Define encryption, backup, retention, device-loss, and incident procedures.
7. Complete a security and privacy review.
8. Test the workflow with fictional data first.

If any required safeguard is missing, stop the real-person research. Continue only with the fictional-data prototype.

## Emergency rule

SehatRaasta is not an emergency service. The interface must tell users to contact local emergency services or a qualified healthcare professional during an emergency.

## Public claims

Use evidence-based claims only. Do not claim clinical impact, reduced delays, reduced costs, or improved outcomes without valid supervised evidence.
