# Phase 6: multilingual appointment form

This is a plain **school-office learning lab**, not the SehatRaasta web app.
Use fictional names only. Its database must be separate from application data.
Urdu and Pashto translations are drafts that need human review.

## Run from the project folder in Git Bash

```bash
source .venv/Scripts/activate
PYTHONPATH=src python learning-labs/phase06_multilingual_form/lab.py --database tmp/phase06-lab/appointments.sqlite
```

Open <http://127.0.0.1:8766/>. Stop with Ctrl+C. The server listens only on
your computer. This is not a deployment server or a real-data security boundary.

- Enter a fictional name, a date such as `2026-09-20`, and confirm synthetic use.
- Save. The list shows the saved request and a text confirmation.
- Submit the same name and date again. The duplicate is rejected.
- Change the interface language. Entered text stays unchanged.
- Open **State examples** for all eleven states. These previews do not save data.
- The print link opens a plain list suitable for browser printing.

The browser checks required fields and the date format first. The server also
checks every submission, including whether a date actually exists. State previews
show server errors without asking you to disable browser validation.

## Files to read in order

1. `src/sehatraasta/presentation/catalogs.py`: messages and language directions.
2. `src/sehatraasta/presentation/errors.py`: shared safe error descriptions.
3. `lab.py`: validation, storage, page functions, request handler, start-up.
4. `src/sehatraasta/presentation/tokens.css`: plain styles and print rules.

The small lab uses Python's built-in HTTP server and SQLite. The future
SehatRaasta Flask interface will call the existing application services instead.

## Checks

```bash
python -m pytest -q tests/unit/test_phase06.py tests/integration/test_phase06_http.py
python -m pytest -q
```

Optional automated browser check: `tests/manual/phase06_browser.cjs` needs Node,
Playwright, Microsoft Edge, and the running lab. It is not a required Python
dependency. Its screenshots and result file go into `tmp/phase06-browser/`.

Also perform the manual checklist in `docs/testing/phase06-checks.md`. Automated
tests do not replace a fluent language reviewer or a screen-reader user.
