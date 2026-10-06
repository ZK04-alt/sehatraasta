# Phase 5 learning notes: print summaries, QR codes, costs, and backups

Prepared: 12 September 2026

These notes explain the concepts behind Phase 5. They are not another set of project implementation tasks.

The examples use a fictional school event ticket. Do not use personal or medical records.

## How to study this phase

Read one section at a time. Predict each example's result before you run it.

You do not need to memorize every method. You need to understand what enters each operation and what comes out.

| Time | Topic | Aim |
| --- | --- | --- |
| 0-10 minutes | Sections 1-3 | Separate stored records, printed summaries, and QR payloads. |
| 10-25 minutes | Sections 4-7 | Understand random IDs, checksums, and QR images. |
| 25-40 minutes | Sections 8-10 | Understand HTML, print CSS, and exact amounts. |
| 40-55 minutes | Sections 11-14 | Understand backup, validation, and restore. |
| 55-60 minutes | Section 15 | Answer the recall questions without looking. |

Treat this hour as your first pass. Return to the examples when a term feels unfamiliar.

## Small glossary

| Term | Meaning here |
| --- | --- |
| Record | One stored item, such as a ticket. |
| Payload | The information inside a message or QR code. |
| Opaque ID | An identifier that does not describe the person or record. |
| Checksum | A value used to detect changes in data. |
| Authentication | Checking whether someone is who they claim to be. |
| Authorization | Checking whether someone may perform an action. |
| Serialization | Converting structured data into a format that can be stored or transferred. |
| Archive | One file that contains other files. |
| Manifest | A list describing the expected contents of a package. |
| Dry run | A check that reports a proposed result without changing the current dataset. |
| Restore | Rebuilding usable data from a backup. |

## 1. What problem does this phase address?

Imagine a school event application. Its database contains tickets, event details, and small supporting files.

The organizer wants three things:

- A readable paper ticket.
- A QR code that helps find the correct local ticket.
- A backup that can rebuild the application data after a failure.

These are three different jobs. One file does not automatically do all three.

A paper ticket can show the event name. The QR can contain only a random ticket ID.

The database connects that random ID to the full record.

The QR does not need to contain everything on the paper.

## 2. Stored data and displayed data are different

Suppose the database contains:

| Field | Fictional value |
| --- | --- |
| Ticket ID | A random identifier |
| Event | School science evening |
| Attendee | Example Guest |
| Seat | C12 |
| Fee | PKR 250.00 |

The printable ticket might show these fields with headings and spacing.

The QR might contain the ticket ID, a format version, and a checksum.

A backup must contain enough information to restore the stored records and supporting files.

Ask this question whenever you export something:

> Is this output for a person to read, a program to look up, or a program to restore?

The answer determines what belongs in it.

## 3. A QR code is not a locked container

A QR code represents data as a pattern of squares. A scanner can decode that pattern.

If the payload contains a name, the scanner can obtain that name.

Changing the name into a QR image does not hide it.

For this prototype, the payload contains only an opaque identifier, a version, and a check value.

The paper can contain sensitive information even when the QR does not. Protecting the QR alone does not protect the paper.

Also separate these ideas:

- Finding a record does not prove who the reader is.
- Knowing an ID does not grant permission to read a record.
- A local lookup works only where the corresponding local data exists.

No cloud connection is necessary for the lookup itself. Another device does not automatically receive the underlying records.

## 4. Generating an opaque identifier

Read the `uuid4()` section in the [Python UUID documentation](https://docs.python.org/3/library/uuid.html).

```python
from uuid import uuid4

ticket_id = uuid4().hex

print(ticket_id)
print(len(ticket_id))
```

### Read it line by line

`from uuid import uuid4` makes the `uuid4` function available.

`uuid4()` creates a random UUID object.

`.hex` gives its hexadecimal text representation without hyphens.

`ticket_id` retains that text. Its length is 32 characters.

The exact output differs between runs. Do not write a test that expects one particular generated ID.

A database still needs a uniqueness rule. Random generation does not replace that rule.

### When should you generate it?

Generate the ID when the record first needs its permanent lookup identity.

Retain the ID after that point. Do not generate another ID whenever someone prints the same ticket.

Otherwise, yesterday's paper could point to an identifier the application no longer recognizes.

**Check yourself:** Does an opaque ID explain the event name? It should not.

## 5. Understanding a checksum

Read `sha256()` and `hexdigest()` in the [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html).

```python
import hashlib

original = "ticket-demo-1"
changed = "ticket-demo-2"

original_check = hashlib.sha256(original.encode("utf-8")).hexdigest()
changed_check = hashlib.sha256(changed.encode("utf-8")).hexdigest()

print(original_check == changed_check)
```

The result is `False`.

### What happens inside the longer line?

Start with `original`, which is text.

`.encode("utf-8")` converts that text into bytes.

`hashlib.sha256(...)` calculates a digest from those bytes.

`.hexdigest()` represents the digest as hexadecimal text.

The digest does not contain a readable copy of the original text. It is not an encrypted copy either.

### What does verification mean?

The receiving program calculates another checksum from the received data. It compares that checksum with the supplied checksum.

A mismatch means the data and checksum do not agree.

**Important limitation:** Someone who changes the data can also calculate a new ordinary checksum.

Therefore, an ordinary checksum detects accidental alteration. It does not prove who created the package.

Digital signatures and keyed authentication are different topics. Do not claim that a plain SHA-256 checksum provides those protections.

## 6. Giving a payload a predictable structure

Python dictionaries and JSON text are not the same type.

```python
import json

ticket_message = {
    "id": "fictional-ticket-example",
    "version": 1,
}

payload = json.dumps(ticket_message)
restored_message = json.loads(payload)

print(type(ticket_message).__name__)
print(type(payload).__name__)
print(restored_message["id"])
```

Expected output:

```text
dict
str
fictional-ticket-example
```

`dumps` converts the dictionary to JSON text. `loads` reads JSON text into Python values.

The example explains serialization only. It is not the complete QR format.

### Why include a version?

A version tells the receiving program which format it must understand.

Version 1 and version 2 might require different fields.

An unknown version needs a clear rejection. Guessing how to interpret it risks incorrect data.

The QR format version and database migration version describe different formats. Their numbers do not have to match.

### Why does consistent text matter?

These strings differ:

```text
{"id":"abc","version":1}
{"id": "abc", "version": 1}
```

They can describe the same information, but they contain different bytes.

A checksum compares bytes, not your intended meaning. Define exactly which fields and separators produce the checked text.

## 7. Turning a payload into an image

Read the basic examples and error-correction section in the [qrcode package documentation](https://pypi.org/project/qrcode/).

Skip styled shapes and decorative logos for now.

Run this independent example in a disposable learning folder:

```python
import qrcode

payload = "fictional-ticket-example"
image = qrcode.make(payload)
image.save("demo-ticket.png")
```

`qrcode.make(payload)` encodes the supplied text into a QR image.

`image.save(...)` writes that image to a PNG file.

The image contains the exact supplied text. The library does not automatically remove sensitive fields.

**Caution:** This example can replace an existing file with the same name. Use a new learning folder.

### Error correction is not an integrity check

QR error correction helps a scanner recover data from some damaged squares.

A payload checksum checks whether the decoded information agrees with the supplied check value.

These protections operate at different stages.

### What should you test?

1. Decode the generated image with a separate decoder.
2. Compare the decoded payload with the intended payload.
3. Decode a rendered print sample.
4. Check the result in grayscale.

A test that only confirms the PNG exists cannot prove that the QR is readable.

Keep a white border around the QR. Do not place text over it.

## 8. HTML and CSS: just enough for printing

HTML describes the content. CSS describes its presentation.

This example contains one heading and one paragraph:

```html
<h1>School science evening</h1>
<p>Seat: C12</p>
```

`<h1>` starts a heading. `</h1>` ends that heading.

`<p>` starts a paragraph. The text between its tags appears as paragraph content.

CSS selects elements and gives them presentation rules:

```css
p {
    color: black;
}
```

`p` selects paragraph elements. `color: black` sets their text color.

The braces contain the rule's declarations. The semicolon ends a declaration.

### Print-specific rules

Read the [MDN printing guide](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing).

```css
@media print {
    nav {
        display: none;
    }
}
```

`@media print` applies its rules to printed output.

`nav` selects navigation elements. `display: none` removes them from that output.

A paper summary does not need navigation or clickable controls.

### Paper size and margins

Read the introductory examples in the [MDN @page reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@page).

```css
@page {
    size: A4;
    margin: 12mm;
}
```

`size: A4` requests A4 paper. `margin: 12mm` requests space around its content.

Print settings and browser behavior can affect the result. Always inspect print preview.

**Privacy check:** Turn browser headers and footers off. Otherwise, the browser can print the local file address.

## 9. Safe text and readable pages

Suppose a fictional event title contains `<demo>`.

The browser must display that text. It must not treat it as an HTML element.

```python
from html import escape

event_title = "Science <demo> & discussion"
safe_title = escape(event_title)

print(safe_title)
```

Expected output:

```text
Science &lt;demo&gt; &amp; discussion
```

These replacements let HTML display special characters as text. Escaping does not encrypt the text.

### Why long text needs its own test

A short example can fit even when the layout is wrong.

Test a long title, a long unbroken word, and several paragraphs.

Keep the first page easy to scan. Place detailed text on continuation pages when necessary.

Each printed page needs enough context to identify it after the pages become separated.

For this prototype, that includes a bundle ID, page number, generation time, and synthetic warning.

Use explicit words such as `pending` and `not reviewed`. Color alone cannot communicate these states reliably on a photocopy.

An offline page must also have its required fonts or fallback fonts and images available locally.

An external image link does not become offline merely because the HTML file is local.

## 10. Exact amounts before attractive formatting

Money must remain exact before you format it for display.

One rupee contains 100 paisa. Integer paisa avoids binary floating-point arithmetic for stored amounts.

```python
amounts_paisa = [250010, 25, 15]
total_paisa = sum(amounts_paisa)

rupees = total_paisa // 100
paisa = total_paisa % 100

print(f"PKR {rupees:,}.{paisa:02d}")
```

Expected output:

```text
PKR 2,500.50
```

`sum(...)` adds the stored integers.

`// 100` gives the whole rupees. `% 100` gives the remaining paisa.

In the formatted string, `:,` adds thousands separators. `:02d` displays at least two integer digits.

Formatting changes how the amount looks. It does not change the stored amount.

When you use `Decimal`, construct amounts from text such as `Decimal("0.10")`.

Converting an existing binary float into `Decimal` does not undo the float's earlier approximation.

### What does the total mean?

A total of reported costs is a total of reported costs.

It does not prove how much the application saved. Measuring savings needs separate evidence and a suitable comparison.

## 11. Export, backup, and restore

| Operation | Fictional ticket example |
| --- | --- |
| Export | Produce a readable summary of one ticket. |
| Backup | Package all records and required supporting files. |
| Restore | Rebuild usable records and files from that package. |

A JSON export containing filenames does not contain the files themselves.

If the originals disappear, their filenames cannot reconstruct their contents.

Likewise, copying files without their database relationships loses important information.

Think of a backup as a matched set: records, files, relationships, and format information.

A successful ZIP creation is only the start. A restore test checks whether that set is usable.

## 12. What goes inside a ZIP?

Focus on `ZipFile`, `writestr`, `namelist`, and `read` in the [Python zipfile documentation](https://docs.python.org/3/library/zipfile.html).

Run this example in a new learning folder:

```python
from zipfile import ZipFile

with ZipFile("demo-ticket-backup.zip", "x") as archive:
    archive.writestr("ticket.txt", "Fictional ticket: seat C12")

with ZipFile("demo-ticket-backup.zip", "r") as archive:
    print(archive.namelist())
    content = archive.read("ticket.txt")
    print(content.decode("utf-8"))
```

Expected output:

```text
['ticket.txt']
Fictional ticket: seat C12
```

`"x"` creates a new archive. It refuses to replace an existing archive.

`writestr` writes content under a name inside that archive.

`"r"` opens the archive for reading. `read` returns bytes, so `decode` converts them into text.

The `with` block closes the archive even if an exception occurs.

This small example teaches the API. It is not a safe general import system.

### Compression is not encryption

Compression can reduce file size. It does not establish who may read the file.

The current synthetic backup is not an encrypted package.

Do not use its existence as evidence that real records are ready for secure cross-device exchange.

## 13. A manifest and a dry run

Imagine a package with three expected members:

```text
dataset.json
attachments/random-name.png
manifest.json
```

The dataset describes the records. The attachment member contains bytes.

The manifest lists expected members and their checksums.

The manifest normally excludes its own checksum. Otherwise, changing the manifest would also change the value it must contain.

The receiving program needs more than checksum comparisons:

1. Check the package version.
2. Check the expected members.
3. Reject duplicate member names.
4. Check size limits.
5. Check each checksum.
6. Validate the records and their relationships.
7. Compare attachment metadata with attachment bytes.

The dry run performs these checks in a temporary location.

It can report record counts, file counts, and totals before the user confirms an import.

Temporary validation files are not changes to the current dataset.

### Why not extract every member immediately?

An archive member can contain a name such as `../../outside.txt`.

A program must not let that name choose an unrestricted destination.

A compressed archive can also expand into much more data than its compressed size suggests.

Validate names, member counts, and expanded sizes before accepting the package.

Use only expected archive members. Do not execute SQL statements supplied inside an imported package.

## 14. Why a fresh restore location matters

Imagine that the current application works, but an imported backup is corrupt.

If import replaces current files before checking the backup, both copies can become unusable.

A safer local prototype restores into a new folder.

The current folder remains available while validation occurs.

This also makes the result easier to inspect. You can compare the restored dataset with the original.

### What should match?

- The number of records in each table.
- Record IDs and relationships.
- Attachment names used internally and their hashes.
- Exact cost totals.
- Permanent QR lookup identifiers.

Counts alone are insufficient. Ten restored records can still contain the wrong values.

Hashes alone are insufficient. Correct file bytes can still connect to the wrong record.

### Why test failure deliberately?

A successful run cannot show what happens when a write fails halfway through.

An automated test can deliberately raise an error at that point.

The test then checks that no partial result remains, or that the documented recovery operation removes it.

For files and SQLite, one SQLite rollback does not automatically undo a filesystem write.

That difference explains why cleanup and reconciliation tests exist.

## 15. Recall questions

Try these before reading the answers:

1. Does a QR image conceal its payload?
2. Why retain the same opaque ID when a record is printed again?
3. What does a checksum mismatch tell you?
4. Can someone change both the data and an ordinary checksum?
5. What is the difference between QR error correction and payload verification?
6. Why can a local HTML file still require the internet?
7. Why disable browser headers and footers before printing?
8. Why store monetary values as integer paisa?
9. Does a JSON file containing attachment names back up their bytes?
10. What does a dry run protect?
11. Why test restore instead of only testing ZIP creation?
12. Does an offline prototype automatically provide authentication or encryption?

### Short answers

1. No. A scanner can decode it.
2. Earlier printouts must retain their local lookup identity.
3. The received data and supplied checksum do not agree.
4. Yes. An ordinary checksum is not proof of authorship.
5. Error correction helps decode damaged squares. Verification checks the decoded payload.
6. Its images, styles, or fonts might use external links.
7. The browser can otherwise print a local file address.
8. Integer arithmetic keeps stored paisa and totals exact.
9. No. The backup must also contain the required file bytes.
10. It lets validation occur before the current dataset changes.
11. A created archive can still be incomplete or unusable.
12. No. Those are separate protections.

## What you do not need to learn yet

Leave decorative QR design, encrypted sharing, cloud synchronization, and automatic document interpretation for later work.

Your goal here is narrower: readable output, a limited local lookup, and a backup that passes a real restore test.

The project remains a synthetic-data prototype. Technical tests do not establish clinical safety or readiness for real patient data.
