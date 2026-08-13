# SehatRaasta

**Synthetic-data offline referral-bundle prototype.**

> **WARNING - Synthetic demonstration - not for clinical use.**
>
> Use fictional data only. Do not enter real patient or medical information.

## Purpose

SehatRaasta is a student-built prototype for organizing fictional referral information and supporting documents.

The planned technical release will show which document categories are present, missing, pending, not applicable, or not reviewed. It will not make clinical decisions.

## Current status

Phase 0 covers safety, repository setup, the domain model, synthetic scenarios, and readiness. Phase 1 is the next development phase.

The repository does not contain working application logic yet. The files under `src/sehatraasta/` are placeholders for later phases.

## Safety limits

- Use fictional records and fictional documents only.
- Do not use the project for a real patient, clinic, or medical decision.
- Do not diagnose a condition.
- Do not interpret clinical text, values, results, or images.
- Do not recommend treatment.
- Do not calculate medical urgency.
- Do not automatically translate clinical text.
- Do not place medical information in QR codes or application logs.
- Do not claim that a referral bundle is medically complete.

Read [SAFETY.md](SAFETY.md) before you use or change the project.

## September non-goals

The technical prototype will not include:

- real patient data;
- a clinic pilot or patient study;
- diagnosis or treatment advice;
- medical urgency calculation;
- automatic clinical translation;
- OCR or medical-image interpretation;
- cloud synchronization;
- a mobile application; or
- claims about clinical impact, reduced delays, reduced costs, or improved outcomes.

These items need different technical, ethical, security, or research evidence. They are not evidence targets for the synthetic technical build.

## Repository contents

- `SAFETY.md`: safety rules and real-person research gates.
- `AI_USE.md`: public record of material AI assistance.
- `docs/domain-model.drawio`: editable domain-model diagram.
- `docs/domain-model.png`: exported domain-model image.
- `docs/synthetic-scenarios.md`: fictional workflow and failure scenarios.
- `learning/domain model/`: Phase 0 learning notes and practice work.
- `src/sehatraasta/`: application package placeholders.
- `tests/`: test folders for later phase work.
- `learning-labs/`: separate practice-lab folders.

## Local setup

Use Git Bash on Windows.

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m pytest --version
```

The project uses Python 3.14.6 in the current local environment. Phase 0 has no application test suite in this repository. The student completed the separate readiness exercise outside this repository.

## Development rules

- Keep domain logic independent from terminal input, Flask, and SQLite.
- Complete each learning lab before the related SehatRaasta work.
- Add tests as behavior is added.
- Keep runtime databases and attachments inside ignored local folders.
- Record material AI assistance in `AI_USE.md`.
- Do not start Phase 2 until the Phase 1 gate passes.

## Evidence boundary

The current evidence shows project planning, safety work, a domain model, synthetic scenarios, and environment setup. It does not show a working product, clinical safety, clinic use, or measured impact.
