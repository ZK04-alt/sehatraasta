# SehatRaasta interface contract

Phase 6, 20 September 2026. Written before the Phase 6 lab HTML.

This contract began as the Phase 6 interface specification. Phase 7 now implements
the local Flask website. It remains a synthetic demonstration, not a production
clinical interface. The separate Phase 6 lab remains unchanged.

The Phase 7 audit is in `phase07-gui-audit.md`. Launch instructions and current
behaviour are in `../phase07-website.md`. The Phase 6 design tokens below describe
the lab; the website uses the approved warm-neutral/navy/teal tokens in
`src/sehatraasta/web/static/app.css`.

## Boundaries

- Synthetic data only. No diagnosis, treatment, urgency, savings, or impact claims.
- Translate interface messages only. Never translate or overwrite stored source text.
- English uses `lang=en dir=ltr`. Urdu uses `lang=ur dir=rtl`. Pashto uses `lang=ps dir=rtl`.
- Urdu and Pashto messages remain `review_pending` until a named human reviews them.
- Keep record identifiers, dates, and PKR amounts in isolated LTR spans. Use `bdi dir=auto` for supplied text.
- A language toggle changes presentation only. On an unsaved form, preserve entered values and validation errors.
- Do not expose storage paths, stack traces, or medical/source text in error logs.
- POST routes require CSRF protection and server validation. Saves use post/redirect/get.
- Local-only does not mean authenticated, encrypted, or ready for patient data.

## Shared states and messages

Every route below inherits these rules where applicable:

| State | Required behavior | Message key / action |
| --- | --- | --- |
| Initial | Visible heading, warning, labels, primary action, help | `warning.synthetic`, page title |
| Loading | Preserve form values; prevent repeated submission while processing | `status.working`, polite status region |
| Empty list | Explain that no records exist; offer creation when permitted | `state.empty`, `action.create` |
| Empty submission | Reject required fields; preserve all other values | `error.required`, summary plus inline error |
| Invalid | Identify field, problem, correction; focus summary | `error.summary`, field-specific code |
| Success | Confirm action in text; identify saved record; do not rely on green | `status.saved`, `status.exported`, `status.deleted` |
| Duplicate | No second write; retain values; link existing record when safe | `error.duplicate` |
| Unavailable | No false success; retain values; allow deliberate retry | `error.unavailable`, `action.retry` |
| Not found | Safe 404; explain missing record; link list | `error.not_found`, `action.back` |
| Unexpected error | Safe 500; no technical exception text; no claimed save | `error.unexpected`, `action.back` |
| Print | Hide navigation/actions; retain warning, ID, page context and source text | `action.print` |

Static read-only pages do not have invalid-submission or save-success states.
Lists have no field errors. Downloads have no empty-form state. Destructive
actions require confirmation; cancellation performs no write.

## Routes, titles, fields, and primary actions

These paths describe the local Flask layer. `{id}` means a record route
parameter, not a filesystem path. GET displays; POST validates and changes state.

| Route and methods | Title key | Fields / content | Primary action and result |
| --- | --- | --- | --- |
| `/` GET | `page.home` | Warning, language selector, links | `action.bundles` |
| `/patients` GET | `page.patients` | Synthetic IDs, display names | `action.create` -> new patient |
| `/patients/new` GET/POST | `page.patient_new` | ID, name, birth year, preferred language | `action.save` -> `status.saved` |
| `/patients/{id}` GET | `page.patient` | Patient fields, retained bundles | `action.bundle_new` |
| `/bundles` GET | `page.bundles` | IDs, source, destination, status | `action.bundle_new` |
| `/bundles/new` GET/POST | `page.bundle_new` | Patient ID, bundle ID, creation time, source facility, destination, status | `action.save` -> bundle detail |
| `/bundles/{id}` GET | `page.bundle` | All record groups, exact total, review times, sources | `action.edit` |
| `/bundles/{id}/edit` GET/POST | `page.bundle_edit` | Source facility, destination, referral status | `action.save` -> `status.saved` |
| `/bundles/{id}/medications/new` GET/POST | `page.medication` | ID, verbatim name, strength, dose, route, frequency, duration, instructions, source | `action.save` |
| `/bundles/{id}/orders/new` GET/POST | `page.order` | Name, date, source, workflow status | `action.save` |
| `/bundles/{id}/results/new` GET/POST | `page.result` | ID, name, date, source, interpretation, optional order ID | `action.save` |
| `/bundles/{id}/imaging/new` GET/POST | `page.imaging` | ID, modality, body part, date, facility, report, optional attachment ID | `action.save` |
| `/bundles/{id}/instructions/new` GET/POST | `page.instruction` | Category, source language, verbatim text, source, date | `action.save` |
| `/bundles/{id}/attachments` GET | `page.attachments` | Metadata and IDs only; no previews | `action.upload` |
| `/bundles/{id}/attachments/new` GET/POST | `page.attachment_new` | ID, synthetic confirmation, file, category, date, provenance type, source/reference, optional one target | `action.upload` -> `status.saved` |
| `/attachments/{id}/download` GET | `page.download` | ID-based lookup; verified bytes | `action.download`; missing file -> safe error plus audit |
| `/attachments/{id}/delete` GET/POST | `page.delete` | ID, confirmation | `action.delete` -> `status.deleted`; missing disk file still audited |
| `/bundles/{id}/costs` GET | `page.costs` | Category, date, exact amount, source, total | `action.cost_new` |
| `/bundles/{id}/costs/new` GET/POST | `page.cost_new` | ID, category, PKR text, date, source type/reference, source, note | `action.save` |
| `/bundles/{id}/reviews` GET/POST | `page.reviews` | Category, presence state, reviewer, time, note | `action.save`; no review remains not reviewed |
| `/bundles/{id}/audit` GET | `page.audit` | IDs, time, fixed action and outcome only | `action.back` |
| `/bundles/{id}/print` GET | `page.print` | Phase 5 summary, safe QR, original text | `action.print` |
| `/bundles/{id}/export` POST | `page.export` | Bundle ID | `action.export` -> `status.exported` |
| `/lookup` GET/POST | `page.lookup` | QR payload or short lookup ID | `action.find`; altered/missing/ambiguous -> error |
| `/backups` GET/POST | `page.backup` | Complete synthetic dataset | `action.backup` -> `status.exported` |
| `/restore` GET/POST | `page.restore` | Archive, dry run, new destination, confirmation | `action.check` before `action.restore`; current data unchanged |
| Unmatched path GET | `error.not_found` | Safe explanation and return link | `action.back` |
| Unexpected failure | `error.unexpected` | Safe explanation; no traceback | `action.back` |

Phase 7 refinements to the original route table:

- `/` shows the bundle queue directly.
- Bundle creation returns to the queue, where the new bundle can be opened.
- The result form uses the existing service's optional order name, not a new order-ID rule.
- Bundle costs and attachment-list addresses show the complete bundle detail.
- Restore generates a destination folder. A browser cannot submit a filesystem path.
- Successful downloads use the browser download interface rather than a false pre-download confirmation.
- Terms, privacy and a local favicon are included.

## Field and error rules

Required text rejects blank or whitespace-only input. IDs use domain validation.
Dates use ISO values; datetime fields remain distinct. Enumerated choices come
from the domain. Money uses Decimal/integer paisa, not float. Cost/source and
attachment/link rules stay in services. Browsers do not become the authority.

Errors use `UIError(code, field, status)` from `presentation/errors.py`.
The CLI presents the same code as text. The Flask adapter uses the same
object for HTTP status, error summary, and inline messages. Never translate by
searching/replacing clinical text. Unknown errors use a safe generic message.

| Validation condition | Code | Correction |
| --- | --- | --- |
| Required field blank | `error.required` | Enter a value in the named field. |
| Invalid ID | `error.id` | Use the documented ID format. |
| Invalid date | `error.date` | Enter a real date in YYYY-MM-DD form. |
| Unknown enum/state/language | `error.choice` | Select one listed option. |
| Invalid monetary amount | `error.amount` | Use an allowed exact amount with at most two decimals. |
| Duplicate ID/content | `error.duplicate` | Reuse the existing record or choose a new valid ID. |
| Missing bundle/link/file | `error.not_found` | Return to the list and select an existing item. |
| Unsupported attachment | `error.file` | Select an allowed small synthetic file. |
| Storage failure | `error.unavailable` | Retry after storage becomes available. |
| Unclassified failure | `error.unexpected` | Return safely; do not display exception details. |

Error summary links target the exact invalid input ID. Inputs use `aria-invalid`
and `aria-describedby` referencing help and inline error IDs. Preserve valid
values after rejection. Success uses a polite status region. Focus remains
visible for links, buttons, fields, error summaries, and the main heading.

## Design tokens

The executable sheet is `src/sehatraasta/presentation/tokens.css`. Keep it plain.

| Token | Value / purpose |
| --- | --- |
| Surface / text | white / #17212b |
| Muted text | #465465 on white |
| Link / focus | #1649a0; underline links; 3px outline with 3px offset |
| Error | #9b1c1c plus text, not color alone |
| Border | #667085, 1px |
| Spacing | .25rem, .5rem, 1rem, 1.5rem, 2rem |
| Type | 1rem body, 1.5rem heading, line-height 1.6 |
| Controls | At least 2.75rem block size; visible label; no placeholder-only label |
| Layout | Max 48rem; fluid inline size; logical margins and padding |

Do not mirror text with transforms or reverse strings. Keep DOM order meaningful
without CSS. No animations, gradients, icon-only actions, or polished screens.

## Wireframes

See `docs/design/phase06-wireframes.txt`: list, detail, form, failure, and print
layouts cover the route families above. RTL mirrors structural alignment, not
record contents or source wording.

## Evidence boundary

Automated tests can check keys, states, storage preservation, HTML relationships,
keyboard operation, reflow and contrast. They cannot certify natural Urdu/Pashto
wording or establish that Windows Narrator announces everything correctly.
Record those manual checks honestly in `docs/testing/phase06-checks.md`.
