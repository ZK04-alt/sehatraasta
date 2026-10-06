Resources:

1. [W3C — Structural markup and right-to-left text](https://www.w3.org/International/questions/qa-html-dir)
   - `lang`, `dir="rtl"`, `dir="auto"`, and mixed-direction text
2. [WCAG 2.2 — Error identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html)
   - Identifying a problem and the field that contains it
3. [WCAG 2.2 — Status messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
   - Success messages and updates that do not move focus
4. [MDN — Form validation](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation)
   - Native HTML checks and why server validation is still necessary

Date prepared: 20-Sep-2026

notes:

## HCI, interface text, and stored information

HCI:

HCI means Human–Computer Interaction.

It concerns how people use a program and understand its responses.

A program can store data correctly but still be difficult to use.

Example:

A form rejects a date and displays:

```text
Invalid input
```

The validation might be correct, but the message does not identify the field or explain the correction.

A clearer message:

```text
Appointment date: enter a real date in YYYY-MM-DD format.
```

This identifies the field, the problem, and the expected format.

Important mental model:

Correct internal behavior is one part of a usable program.

The person also needs to understand what happened and what action is available next.


Interface text:

Interface text includes headings, field labels, buttons, help, and error messages.

Example:

```text
Name
Appointment date
Save
Record saved
```

These messages belong to the interface.


Stored information:

Stored information is the content entered into a record.

Example:

```text
Name: Demo مثال
Appointment date: 2026-09-20
Reference: AP-001
```

Changing the interface language can change the label “Name”.

It must NOT change the stored value `Demo مثال`.

The same applies to original instructions, document wording, and other source text.

Beginner trap:

Translating the interface does not mean translating every string in the database.

The program selects different interface messages. It keeps source information unchanged.


Learning outcomes for this section:

I should understand what HCI means.

I should distinguish interface text from stored information.

I should understand why a language change must not rewrite source text.


## HTML elements, attributes, `lang`, and `dir`

HTML:

HTML describes the structure of a web page.

Example:

```html
<h1>Appointment request</h1>
```

Break this down:

`<h1>`
starts a main heading.

`Appointment request`
is the heading text.

`</h1>`
ends the heading.

Together, these form an HTML element.


Attributes:

An attribute gives extra information about an element.

Example:

```html
<html lang="ur" dir="rtl">
```

`html`
is the root element containing the page.

`lang="ur"`
identifies the page language as Urdu.

`dir="rtl"`
sets the base text direction to right-to-left.


The three language settings:

```html
<html lang="en" dir="ltr">
```

English, left-to-right.

```html
<html lang="ur" dir="rtl">
```

Urdu, right-to-left.

```html
<html lang="ps" dir="rtl">
```

Pashto, right-to-left.

These are separate examples, not three root elements in one page.


`lang` versus `dir`:

`lang` identifies the LANGUAGE.

`dir` identifies the DIRECTION.

A screen reader can use language information when choosing how to pronounce text.

Direction affects the ordering and layout of text.

Beginner trap:

Putting text on the right side of the page does not make the document structurally RTL.

Alignment and direction are different jobs.

Another trap:

Reversing an Urdu string in Python is not a way to create an RTL interface.

The text stays in its normal stored order. The browser handles its display direction.


Learning outcomes for this section:

I should recognise an element, a tag, and an attribute.

I should explain the difference between `lang` and `dir`.

I should know that right alignment alone does not create correct RTL behavior.


## Mixed-direction text, `bdi`, and `dir="auto"`

Mixed-direction text:

A sentence can contain text with different reading directions.

An Urdu sentence might contain an English reference such as `AP-001` or a date such as `2026-09-20`.

Punctuation and numbers can appear in confusing positions when surrounding text affects their direction.


`bdi`:

`bdi` means bidirectional isolation.

It separates the enclosed text's direction from surrounding text.

Basic pattern:

```html
<bdi dir="ltr">AP-001</bdi>
```

Break this down:

`<bdi>`
starts an isolated piece of text.

`dir="ltr"`
specifies left-to-right direction for that piece.

`AP-001`
is the original value.

`</bdi>`
ends the isolated piece.

The program does not reverse or translate the reference.


Dates:

```html
<bdi dir="ltr">2026-09-20</bdi>
```

The date remains in year-month-day order inside surrounding RTL text.

This also matters in help text. A date example needs correct direction, not only a saved date.


`dir="auto"`:

This lets the browser determine direction from the text's first strongly directional character.

Example:

```html
<bdi dir="auto">Demo مثال</bdi>
```

This is useful when supplied text might start in English, Urdu, or Pashto.

Important distinction:

`dir="auto"` determines direction. It does not identify or translate the language.

Isolation also does not guarantee that every mixed-script sentence looks correct.

IDs, dates, units, brackets, and punctuation still need visual review.


Learning outcomes for this section:

I should understand why mixed-direction text needs separate attention.

I should recognise when an ID or date needs `dir="ltr"`.

I should explain what `bdi` and `dir="auto"` do without confusing them with translation.


## CSS and logical properties

CSS:

CSS controls the appearance of HTML elements.

HTML describes the structure. CSS describes how that structure looks.

Example:

```css
.warning {
    border-inline-start: 4px solid #667085;
    padding-inline-start: 1rem;
}
```

Break this down:

`.warning`
selects elements with `class="warning"`.

`border-inline-start`
adds a border at the start of the inline direction.

`4px`
sets the border thickness.

`solid`
sets the border style.

`#667085`
sets the border color.

`padding-inline-start: 1rem`
adds space between the starting edge and the content.

`rem` is a size unit relative to the root element's font size.


Physical versus logical properties:

`padding-left`
always refers to the physical left side.

`padding-inline-start`
refers to the start of the inline direction.

For normal horizontal English text, the start is the left side.

For normal horizontal Urdu text, the start is the right side.

This lets one CSS rule support both directions.


Inline and block:

The inline direction follows a line of text.

The block direction follows the stack of lines or sections.

For ordinary horizontal text, the block direction runs from top to bottom.

Important mental model:

Logical properties describe layout relative to the writing direction, rather than assuming everything starts on the left.


Learning outcomes for this section:

I should distinguish HTML structure from CSS appearance.

I should explain why logical properties help with LTR and RTL layouts.

I should recognise `padding-inline-start`, `margin-inline`, and `margin-block`.


## Labels, input IDs, names, and help text

Visible labels:

A label explains what belongs in a field.

Basic pattern:

```html
<label for="name">Display name</label>
<input id="name" name="display_name" type="text" required>
```

Break this down:

`<label>`
creates a label.

`for="name"`
connects the label to the input whose ID is `name`.

`id="name"`
identifies that input within the page.

`name="display_name"`
sets the field name submitted to the server.

`type="text"`
creates a text input.

`required`
tells the browser that a value is necessary.


`id` versus `name`:

`id` identifies the element IN THE PAGE.

`name` identifies the value IN THE SUBMITTED FORM DATA.

They can use the same text, but they do different jobs.

An ID must be unique within a page.


Placeholder text:

A placeholder is a hint displayed inside an empty field.

It disappears when text is entered.

It must not be the only label because the field still needs an explanation after it contains a value.


Connecting help text:

```html
<label for="date">Appointment date</label>
<p id="date-help">Use YYYY-MM-DD.</p>
<input id="date" name="date" aria-describedby="date-help">
```

`id="date-help"`
identifies the help paragraph.

`aria-describedby="date-help"`
connects the input to that paragraph as its description.

ARIA supplies accessibility information to assistive technology.

It does not replace ordinary HTML labels or add server validation.

Beginner trap:

A visible paragraph beside a field is not automatically connected to that field for assistive technology.


Learning outcomes for this section:

I should explain why `for` must match the input's ID.

I should distinguish `id` from `name`.

I should understand why a placeholder is not a replacement for a label.

I should know what `aria-describedby` connects.


## Browser validation and server validation

Browser validation:

This happens in the browser before the form is submitted normally.

Example:

```html
<input name="date" required pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}">
```

`required`
rejects an empty value during normal browser form validation.

`pattern`
checks the shape of a non-empty value.

The pattern describes four digits, a hyphen, two digits, another hyphen, and two digits.

Example that matches the shape:

```text
2026-09-20
```

Another value with the same shape:

```text
2026-02-31
```

The second value is not a real date.

Important distinction:

Correct FORMAT does not always mean valid DATA.


Server validation:

The server checks the submitted data before the program accepts it.

Example:

```python
from datetime import date

text = "2026-02-31"

try:
    appointment_date = date.fromisoformat(text)
except ValueError:
    print("Enter a real date")
```

`date.fromisoformat(text)`
attempts to create a Python date from the text.

The impossible date raises `ValueError`.

The example catches that error and displays a simple explanation.

In application code, the validation layer can return or raise an error instead. The interface decides how to display it.

Beginner trap:

Browser validation is not a security boundary.

A request can reach the server without using the displayed form. The server must check the data independently.


Learning outcomes for this section:

I should distinguish browser checks from server checks.

I should understand why a date pattern does not prove that a date exists.

I should know why both layers need validation.


## Error summaries, inline errors, and preserved values

Inline error:

An inline error appears next to the field with the problem.

Example:

```html
<label for="date">Appointment date</label>
<input id="date" name="date" value="2026-02-31"
       aria-invalid="true" aria-describedby="date-error">
<p id="date-error">Enter a real date in YYYY-MM-DD format.</p>
```

`aria-invalid="true"`
marks the input as invalid for assistive technology.

It does not perform the validation itself.

`aria-describedby="date-error"`
connects the input to its error explanation.

`value="2026-02-31"`
retains the submitted value so the person can correct it.

If help and an error both exist, both IDs can appear in `aria-describedby`, separated by spaces.


Error summary:

An error summary collects the problems near the top of the form.

Example:

```html
<section tabindex="-1" aria-labelledby="error-heading">
    <h2 id="error-heading">Check the following fields</h2>
    <a href="#date">Appointment date: enter a real date.</a>
</section>
```

`href="#date"`
links to the element whose ID is `date` on the same page.

`tabindex="-1"`
allows the section to receive focus through code without adding it to the normal Tab sequence.

It does NOT move focus by itself.

`aria-labelledby="error-heading"`
uses the heading as the section's accessible name.

The program needs a deliberate focus strategy after rejection. The person should not have to search the whole page for the problem.


Preserving values:

If only the date is wrong, the name should remain in the form.

Changing the interface language should also preserve unsaved input.

Otherwise, a simple correction becomes repeated data entry.

Beginner trap:

A red border alone is not enough. The error needs readable text and a connection to the field.


Learning outcomes for this section:

I should distinguish an error summary from an inline error.

I should explain how a summary link reaches a field.

I should understand that ARIA attributes describe errors but do not validate data.

I should know why rejected forms retain entered values.


## Success messages, status regions, and alerts

Success message:

A success message confirms a completed operation.

Example:

```html
<p role="status">Record saved.</p>
```

`role="status"`
identifies a status region. Updates normally use a polite announcement rather than interrupting other speech.

This is useful for information that does not require focus to move.

An empty status region can exist before an update. The program then changes its text after the operation finishes.


Alert:

```html
<p role="alert">The request could not be saved.</p>
```

An alert is for important information that needs prompt attention.

Not every update needs an alert. Too many interruptions make the interface harder to use.

Important distinction:

An announcement and keyboard focus are different things.

Adding a role does not automatically move focus to an element.

Screen-reader behavior also needs testing, especially when the entire page reloads rather than updating in place.

Beginner trap:

Finding `role="status"` in the HTML does not prove that Narrator announced the message correctly.


Learning outcomes for this section:

I should understand the purpose of a status region.

I should distinguish polite status updates from urgent alerts.

I should know why real screen-reader checks are still necessary.


## Complete interface states

State:

A state describes the condition the interface currently shows.

It does not necessarily mean a new page or a new database record.

For a fictional appointment form:

| State | Meaning |
| --- | --- |
| Initial | The form is ready for input. |
| Empty submission | Required values were not supplied. |
| One invalid field | One value needs correction. |
| Multiple invalid fields | Several values need correction. |
| Success | The operation completed. |
| Duplicate | The requested record already exists. |
| Empty list | There are no saved records to display. |
| Storage unavailable | The program cannot complete the storage operation. |
| 404 | The requested page or record was not found. |
| 500 | An unexpected server error occurred. |
| Print | Content is arranged for printing rather than interaction. |


Empty list versus storage failure:

An empty list means the program successfully checked and found no records.

A storage failure means the program could not complete that check.

Showing “No records” after a storage failure gives misleading information.


Loading:

A loading state means an operation has not finished.

The interface must not display success before the operation succeeds.

Repeated submissions also need control so one action does not accidentally create several records.


Print:

A print layout keeps useful content and removes controls that have no purpose on paper.

Navigation and save buttons are normally hidden. Warnings, record IDs, and source information remain visible.

The printed layout needs a separate check for clipped text and missing content.


Safe errors:

A public error message must not expose database paths, raw exception text, or private source information.

The interface can explain that saving failed without displaying the internal storage location.


Learning outcomes for this section:

I should consider failure and empty states, not only successful operations.

I should distinguish an empty result from an unavailable data source.

I should know why success must reflect the actual operation result.


## Message catalogs and missing translations

Message catalog:

A catalog stores interface messages under stable keys.

Small learning example:

```python
messages = {
    "en": {"action.save": "Save"},
    "ur": {"action.save": "محفوظ کریں"},
}

language = "en"
text = messages[language]["action.save"]
print(text)
```

Output:

```text
Save
```

Break this down:

`messages`
is a dictionary containing a dictionary for each language.

`messages[language]`
selects the dictionary for the chosen language.

`["action.save"]`
selects the save message within that dictionary.

`text`
contains the selected display text.

Changing `language` changes which interface text is selected. It does not change any appointment record.

The example shows the concept, not the exact catalog structure required in every program.


Missing keys:

Accessing a missing dictionary key with square brackets raises `KeyError`.

The program needs a deliberate policy for missing interface messages.

One visible fallback:

```text
[Missing translation: action.save]
```

An obvious marker makes the missing entry noticeable. A blank button can hide the problem.

Tests can also check that every language contains the required keys and non-empty messages.


Translation review:

Having a translation is not the same as having an approved translation.

Each message can include a review state such as:

```text
review_pending
reviewed
```

Human approval needs an actual reviewer and a record of the review.

Automated tests cannot establish natural wording or clinical meaning.

Clinical source text must not be automatically translated as interface text.


Shared error descriptions:

The same error can appear in a CLI and a web interface.

A shared description can contain:

```text
code: error.required
field: date
status: 422
```

`code`
selects the message.

`field`
identifies where the problem occurred.

`status`
can provide the HTTP response status for a web interface.

The CLI can show text. The web interface can connect the same error to a form field.

The service still performs the operation and validation. The interface decides how to present the result.


Learning outcomes for this section:

I should explain how a stable key selects different display text.

I should understand why a missing message needs visible handling or a failing test.

I should distinguish translation availability from human review.

I should understand why shared errors do not move business rules into the interface.


## Keyboard access, focus, headings, contrast, and reflow

Keyboard access:

The main actions should work without a mouse.

Common controls:

`Tab` moves to the next focusable control.

`Shift+Tab` moves back.

`Enter` activates a focused link or button.

`Space` changes a focused checkbox.

Ordinary HTML buttons, links, and inputs already provide useful keyboard behavior.

A decorative box with a click handler does not automatically provide the same behavior.


Focus:

Focus identifies the element that receives keyboard input.

A visible outline helps show which control is active.

Example:

```css
:focus {
    outline: 3px solid #1649a0;
    outline-offset: 3px;
}
```

`:focus`
selects the focused element.

`outline`
draws the visible focus indicator.

`outline-offset`
adds space between the element and its outline.

Removing focus indicators makes keyboard navigation difficult to follow.


Headings:

Headings describe the page's structure, not just its font sizes.

An `h1` identifies the main page heading. An `h2` identifies a section below it.

A paragraph styled with large text does not automatically become a heading for assistive technology.


Contrast:

Text needs enough contrast against its background to remain readable.

Error meaning must not depend on color alone.

Text such as “The date is invalid” remains useful even when the red styling is not visible.


Reflow:

Reflow means content adjusts when the available display space changes.

At a narrow width, controls and text should fit without unnecessary horizontal page scrolling.

Two different checks:

1. A viewport 320 CSS pixels wide.

2. Native browser zoom at 200%.

These are related checks, but they are not identical.

A CSS zoom simulation also does not replace the native browser zoom check.


CSS disabled:

Without CSS, headings, labels, help, and controls should still follow a meaningful order.

This checks whether the document structure makes sense without visual arrangement.


Screen reader:

A screen reader presents interface information through speech or other accessible output.

Windows Narrator checks need to cover labels, descriptions, errors, navigation, and success feedback.

Important mental model:

Automated tests check specific properties. Human checks establish whether the interaction makes sense in actual use.


Learning outcomes for this section:

I should understand focus and its visible indicator.

I should know why headings and native controls matter.

I should distinguish narrow-width checks from browser zoom checks.

I should understand why automated checks do not prove complete accessibility.


## Interface contracts, design tokens, and wireframes

Interface contract:

An interface contract records what each planned page must contain and how it responds to different states.

It includes the route, title, fields, main action, success response, and error behavior.

Example:

```text
Page: New appointment
Fields: name and date
Action: save
Success: show the saved appointment
Invalid input: retain values and explain each problem
Duplicate: reject the second record
Storage failure: explain that saving was not confirmed
```

This defines behavior before detailed page styling.


Route:

A route is an address handled by the program.

GET normally retrieves information.

POST submits an operation that can change state.

After a successful POST, the program can redirect to a GET page. Refreshing that page does not repeat the original POST.


Design tokens:

These are shared appearance values, such as text colors, spacing, borders, and focus styles.

Example:

```css
:root {
    --space: 1rem;
}

main {
    padding: var(--space);
}
```

`--space`
defines a CSS custom property.

`var(--space)`
uses its value.

Shared values keep related pages consistent.


Wireframe:

A wireframe is a simple layout showing where content and controls belong.

It can contain only boxes or plain text.

Its purpose is to check structure, not create a finished visual design.


Learning outcomes for this section:

I should distinguish an interface contract from page code.

I should understand the purpose of shared appearance values.

I should know why a wireframe does not need polished styling.


## Write answers

1. Why are `lang` and `dir` both necessary?

They describe different properties.

`lang` identifies the language. `dir` identifies the text direction.

Right alignment alone does not provide either complete language information or correct structural direction.


2. Why must original source text remain unchanged when the interface language changes?

Interface messages belong to the program's presentation.

Source text belongs to the stored record.

Changing a display preference is not permission to rewrite the record or alter its meaning.


3. What makes an error message useful?

It identifies the problem, connects it to the correct field, and explains a correction when one is known.

The form retains valid values. The explanation does not depend on color alone.


4. Why are server checks needed when the browser already validates the form?

Browser checks can be bypassed.

The server receives requests, not proof that a person used the intended form.

The program must validate submitted data before accepting it.


5. Why do Urdu and Pashto messages need review even when all tests pass?

Tests can check missing keys, HTML direction, and unchanged stored values.

They cannot prove that the wording is natural or carries the intended meaning.

A fluent human review is separate evidence. Clinical terminology needs suitable professional review before real use.


6. Why is an empty list different from a storage failure?

An empty list is a successful result containing no records.

A storage failure means the program could not complete the operation.

Displaying the same message for both could falsely suggest that saved records do not exist.


7. What remains outside automated accessibility checks?

Actual screen-reader announcements, fluent language review, and the quality of mixed-script reading need human checks.

Native browser zoom and CSS-disabled reading order also need the stated manual checks when only simulations or structural assertions exist.

Passing tests are evidence of the properties tested, not a complete accessibility certificate.
