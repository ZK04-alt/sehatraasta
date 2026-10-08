> Personal learning notes kept for Zunair Ali Khan to learn. These are separate from the app and its release evidence.

Resources:

1. [CS50P - Lecture 6 - File I/O](https://www.youtube.com/watch?v=KD-Yoel6EVQ&t=354s)
   - 00:05:54-00:21:39: `open`, closing files, `with`, and reading lines
   - 00:57:13-01:20:37: structured CSV reading and writing
2. [Python JSON module](https://docs.python.org/3/library/json.html)
   - Basic encoding/decoding and the repeated-file warning
3. [Python pathlib](https://docs.python.org/3/library/pathlib.html)
   - Creating and joining paths only
4. [Python argparse tutorial](https://docs.python.org/3/howto/argparse.html)
   - Positional arguments, options, and help
5. [Python decimal module](https://docs.python.org/3/library/decimal.html)
   - Quick-start examples and exact decimal arithmetic only

Date watched: 30-Aug-2026

notes:

## File I/O, `open()`, closing files, `with`, and reading lines

File I/O:

I/O means Input/Output.

File input means my program reads information FROM a file.

File output means my program writes information TO a file.

Variables only keep their values while the program is running.
A file lets information remain after the program ends so it can be read again later.


`open()`:

`open()` gives my program access to a file.

Basic pattern:

```python
file = open("names.txt", "a", encoding="utf-8")
```

Break this down:

`open(...)`
asks Python to open a file.

`"names.txt"`
is the path to the file I want to use.

`"a"`
tells Python HOW I want to use the file.

`encoding="utf-8"`
tells Python how text characters should be stored/read.

`file =`
stores the opened file object in the variable `file` so I can work with it.

Important mental model:

`open()` does NOT give me the contents of the file directly.

It gives me a file object that I can then read from or write to.


The three file modes I need here:

`"r"` = read

Use this when I want to get information from an existing file.

Example:

```python
file = open("names.txt", "r", encoding="utf-8")
```

`"r"` is also the default mode.

Therefore:

```python
open("names.txt", encoding="utf-8")
```

means the same basic thing as:

```python
open("names.txt", "r", encoding="utf-8")
```


`"w"` = write

Use this when I want to write a new version of the file.

If the file does not exist, Python creates it.

IMPORTANT: if the file already exists, `"w"` replaces its existing contents.

Example:

File currently contains:

```text
Harry
Hermione
```

If I open it using `"w"` and write `Ron`, the old contents are replaced.

It will then contain only:

```text
Ron
```

Beginner trap:

Do not think `"w"` means "add another thing to the file".

Think:

`"w"` = write a new version of this file.


`"a"` = append

Append means add new content to the end of the existing file.

If the file does not exist, Python creates it.

If it already exists, the old contents remain and new content is added after them.

Example:

```python
file = open("names.txt", "a", encoding="utf-8")
file.write("Ron\n")
file.close()
```

If the file already contained Harry and Hermione, Ron is added after them rather than replacing them.


`write()`:

An opened file has a `write()` method that writes text into it.

Example:

```python
file.write("Harry")
```


If I want each value on its own line, I include `\n` myself:

```python
file.write("Harry\n")
file.write("Ron\n")
```

`\n` means newline.


Why files need to be closed:

After I finish using a file, I should close it.

Manual way:

```python
file = open("names.txt", "a", encoding="utf-8")
file.write("Harry\n")
file.close()
```

`file.close()` tells Python that I am finished with that opened file.

The problem is that I have to REMEMBER to call `close()` myself.

If the program becomes longer, or something goes wrong before it reaches `close()`, it is easy to leave the file open accidentally.


Context manager: `with`

The safer and normal Python pattern is to use `with`.

Example:

```python
with open("names.txt", "a", encoding="utf-8") as file:
    file.write("Harry\n")
```

Read this almost like English:

WITH this file opened in append mode AS `file`,
do the indented work below.

Step by step:

1. Python opens `names.txt`.

2. The opened file is available through the variable `file`.

3. Python runs the indented code inside the `with` block.

4. When the block finishes, Python closes the file automatically.

The indentation matters:

```python
with open("names.txt", "a", encoding="utf-8") as file:
    file.write("Harry\n")

print("Finished")
```

`file.write(...)` is inside the context where the file is open.

`print("Finished")` is outside it. By then, the file has been closed.

Mental model:

`with open(...) as file:` creates a safe temporary period during which I use the file.

When that period ends, Python handles the closing for me.


Reading a text file with `readlines()`:

Suppose `names.txt` contains:

```text
Harry
Hermione
Ron
```

I can read all its lines using:

```python
with open("names.txt", "r", encoding="utf-8") as file:
    lines = file.readlines()
```

`readlines()` returns a LIST.

Conceptually, `lines` will look like:

```python
["Harry\n", "Hermione\n", "Ron\n"]
```

Notice that each line normally still contains its newline character `\n`.


Why `rstrip()` appears when reading lines:

If a line from the file is:

```python
"Harry\n"
```

then:

```python
line.rstrip()
```

removes whitespace from the right-hand end, including that final newline.

In the CS50 example this prevents extra blank lines when the value is printed.

Example:

```python
with open("names.txt", "r", encoding="utf-8") as file:
    lines = file.readlines()

for line in lines:
    print(line.rstrip())
```


Reading a file one line at a time:

I do not have to call `readlines()` first.

Python lets me loop directly over the opened file:

```python
with open("names.txt", "r", encoding="utf-8") as file:
    for line in file:
        print(line.rstrip())
```

On each loop:

first iteration:
`line` contains the first line

second iteration:
`line` contains the second line

and so on until the file ends.

This is an important pattern to recognize:

```python
for line in file:
```

means:

"give me each line from this file one at a time."


Encodings:

A text file must have a way to translate written characters into data the computer stores.
That translation system is called an encoding.

UTF-8 is a widely used text encoding that can represent English and many other writing systems.

For text files, I should make the encoding explicit:

```python
with open("names.txt", "r", encoding="utf-8") as file:
    for line in file:
        print(line.rstrip())
```

Why explicitly write `encoding="utf-8"`?

It makes the program clear about how the text should be interpreted rather than relying on a machine's default text encoding.

Important distinction:

File encoding such as UTF-8 is about how TEXT CHARACTERS are stored in a file.

Later, the JSON documentation also uses the words "encode" and "decode".
There, the idea is converting between Python data and JSON data.

These are related words, but they are not the same job.


What happens if a file is missing:

The result depends on the mode.

Reading a missing file:

```python
with open("missing.txt", "r", encoding="utf-8") as file:
    ...
```

Python cannot read a file that does not exist, so it raises:

```text
FileNotFoundError
```

Beginner mental model:

`"r"` expects the file to already exist.


Writing to a missing file with `"w"`:

Python creates the file.


Appending to a missing file with `"a"`:

Python also creates the file.


Therefore remember:

`r` + missing file -> `FileNotFoundError`

`w` + missing file -> creates file

`a` + missing file -> creates file

If I EXPECT that a file might be absent, I can handle the specific error with the exception skills I already know:

```python
try:
    with open("names.txt", "r", encoding="utf-8") as file:
        for line in file:
            print(line.rstrip())
except FileNotFoundError:
    print("File not found")
```

The important idea here is not to memorize this exact example.
It is to understand that a missing file while reading is a normal failure Python can report with `FileNotFoundError`.


Learning outcomes for this section:

I should be able to explain what File I/O means.

I should know what `open()` returns and why I store it in a variable.

I should know the difference between `r`, `w`, and `a`.

I should know that `w` can overwrite existing contents.

I should know that `a` adds to the end instead.

I should know that `write()` does not automatically add `\n`.

I should understand why `with open(...) as file:` is safer than manually calling `close()`.

I should be able to read lines using either `readlines()` or `for line in file`.

I should understand why `rstrip()` is used in the CS50 example.

I should know why `encoding="utf-8"` is written explicitly for text files.

I should know what happens when I try to read a file that does not exist.


## Structured CSV reading and writing

CSV:

CSV means Comma-Separated Values.

It is a text format for tabular data: rows and columns.

Example:

```text
name,home
Harry,"Number Four, Privet Drive"
Ron,The Burrow
```

Think of this as a small table:

| name  | home                       |
|-------|----------------------------|
| Harry | Number Four, Privet Drive  |
| Ron   | The Burrow                 |

Each line is a row.

Values in a row are separated into columns.


Why manually using `.split(",")` is fragile:

At first it may seem reasonable to do:

```python
name, home = line.rstrip().split(",")
```

This works for a line such as:

```text
Ron,The Burrow
```

because there is one comma separating exactly two values.

But consider:

```text
Harry,"Number Four, Privet Drive"
```

The HOME itself contains a comma.

A simple `.split(",")` cannot understand that one comma is part of the address while another comma separates CSV columns.

That is why Python's standard-library `csv` module should parse CSV instead of me trying to manually split the text.


Importing the CSV module:

```python
import csv
```

This gives me Python's standard CSV reading and writing tools.


`csv.reader`:

Basic pattern:

```python
import csv

with open("students.csv", "r", encoding="utf-8") as file:
    reader = csv.reader(file)

    for row in reader:
        print(row)
```

Step by step:

1. `open(...)` opens the text file.

2. `csv.reader(file)` creates a CSV reader that knows how to interpret CSV structure.

3. `for row in reader:` gives me one CSV row at a time.

4. With `csv.reader`, each `row` is a LIST.

For this CSV:

```text
Harry,"Number Four, Privet Drive"
```

the reader can give a row equivalent to:

```python
["Harry", "Number Four, Privet Drive"]
```

The comma inside the address is kept as part of the address instead of incorrectly becoming another column.


Accessing values from `csv.reader`:

Because each row is a list, list indexes are used.

```python
row[0]
```

means the first column.

```python
row[1]
```

means the second column.

Example:

```python
import csv

with open("students.csv", "r", encoding="utf-8") as file:
    reader = csv.reader(file)

    for row in reader:
        name = row[0]
        home = row[1]
        print(name, home)
```

Beginner warning:

`row[0]` does NOT mean "the name column" by itself.

It only means "the first column".

If somebody changes the column order, the meaning of `row[0]` changes too.


CSV headers:

A header is the first row that gives names to the columns.

Example:

```text
name,home
Harry,"Number Four, Privet Drive"
Ron,The Burrow
```

Here:

`name` is the name of the first column.

`home` is the name of the second column.

The header is not another student's data.
It describes what each column means.


`csv.DictReader`:

When a CSV has headers, `csv.DictReader` can use those header names.

Example:

```python
import csv

with open("students.csv", "r", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    for row in reader:
        print(row["name"])
        print(row["home"])
```

The major difference:

`csv.reader` -> each row behaves like a LIST

`csv.DictReader` -> each row behaves like a DICTIONARY

With `DictReader`, a row can conceptually look like:

```python
{
    "name": "Harry",
    "home": "Number Four, Privet Drive"
}
```

This means I access data by its meaning:

```python
row["name"]
```

instead of only by its position:

```python
row[0]
```

Why this is useful:

Suppose the CSV changes from:

```text
name,home
```

to:

```text
home,name
```

If the headers are still correct, `row["name"]` still means the name.

Code that assumes `row[0]` is always the name is more dependent on column position.


Writing CSV with `csv.writer`:

Reading gets information FROM a CSV.
Writing puts information INTO a CSV.

Basic pattern:

```python
import csv

name = "Harry"
home = "Number Four, Privet Drive"

with open("students.csv", "a", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow([name, home])
```

Step by step:

`csv.writer(file)`
creates a CSV writer connected to that file.

`writer.writerow(...)`
writes ONE row.

`[name, home]`
is the list of values that should be placed in that row.

The CSV module handles CSV formatting for me.

If `home` contains a comma, the module can quote it correctly in the CSV file.

I should not manually build a line like:

```python
file.write(name + "," + home)
```

when I am trying to write proper CSV structure.


Writing CSV with `csv.DictWriter`:

If I want to write rows using meaningful field names rather than only list positions, I can use `DictWriter`.

Example:

```python
import csv

name = "Harry"
home = "Number Four, Privet Drive"

with open("students.csv", "a", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=["name", "home"])
    writer.writerow({"name": name, "home": home})
```

Break this down:

`csv.DictWriter(...)`
creates a CSV writer that expects dictionary data.

`file`
is the file being written to.

`fieldnames=["name", "home"]`
tells the writer which CSV columns exist and the order in which those columns should be written.

`writer.writerow({...})`
writes one row using a dictionary.

The dictionary:

```python
{"name": name, "home": home}
```

means:

put the value in `name` under the `name` column

put the value in `home` under the `home` column


`reader` vs `DictReader`:

`csv.reader`:

row is a list

access with positions such as `row[0]`


`csv.DictReader`:

row is a dictionary

access with field names such as `row["name"]`


`writer` vs `DictWriter`:

`csv.writer`:

give `writerow()` a list of values

example:

```python
writer.writerow([name, home])
```


`csv.DictWriter`:

define field names

give `writerow()` a dictionary

example:

```python
writer.writerow({"name": name, "home": home})
```


Learning outcomes for this section:

I should understand what rows and columns mean in a CSV file.

I should understand why manually splitting CSV lines on every comma can fail.

I should know why the standard-library `csv` module handles CSV structure for me.

I should know that `csv.reader` gives each row as a list.

I should know that `csv.DictReader` gives each row as a dictionary using the CSV headers.

I should know what a CSV header is.

I should be able to explain the difference between `row[0]` and `row["name"]`.

I should know that `csv.writer(...).writerow(...)` writes a row using a list.

I should know that `csv.DictWriter` writes a row using field names and a dictionary.

I should understand why CSV is naturally suited to flat rows and columns rather than deeply nested data.


## JSON: basic encoding and decoding

JSON:

JSON is a text format for storing structured data.

Python data can be converted into JSON, saved, read later, and converted back into Python data.

JSON can naturally represent nested structures such as dictionaries containing lists and more dictionaries.


Basic Python to JSON idea:

Python dictionary:

```python
profile = {
    "name": "Alex",
    "subjects": ["Maths", "Physics"]
}
```

can be represented in JSON as structured text similar to:

```json
{
    "name": "Alex",
    "subjects": ["Maths", "Physics"]
}
```

The important idea is the conversion:

Python object -> JSON

and later:

JSON -> Python object


Common basic conversions:

Python `dict` -> JSON object

Python `list` or tuple -> JSON array

Python `str` -> JSON string

Python `int` or `float` -> JSON number

Python `True` -> JSON `true`

Python `False` -> JSON `false`

Python `None` -> JSON `null`

Do not get stuck memorising every word immediately.
The main mental model is that common Python containers and values have JSON equivalents.


The four names that are easy to confuse:

`json.dump()`
`json.dumps()`
`json.load()`
`json.loads()`

The final `s` is the important clue.

WITHOUT `s`:

works with a FILE object

WITH `s`:

works with a STRING


`json.dump()`:

Use `dump` when I have a Python object and want to write its JSON representation to an opened file.

Example:

```python
import json

profile = {
    "name": "Alex",
    "year": 2026
}

with open("profile.json", "w", encoding="utf-8") as file:
    json.dump(profile, file)
```

Think:

Python object -> JSON FILE

Step by step:

`profile`
is the Python object I want to save.

`file`
is the opened file where JSON should be written.

`json.dump(profile, file)`
converts the Python data to JSON and writes it to that file.


`json.dumps()`:

`dumps` converts a Python object into a JSON STRING instead of writing directly to a file.

Example:

```python
import json

profile = {"name": "Alex"}
text = json.dumps(profile)
```

`text` is now a Python string containing JSON text.

Think:

Python object -> JSON STRING

Memory trick:

`dumps` = dump to string


`json.load()`:

`load` reads JSON from an opened file and converts it into Python data.

Example:

```python
import json

with open("profile.json", "r", encoding="utf-8") as file:
    profile = json.load(file)
```

After this, `profile` is a Python value again, such as a dictionary.

Think:

JSON FILE -> Python object


`json.loads()`:

`loads` reads JSON from a Python string and converts it into Python data.

Example:

```python
import json

text = '{"name": "Alex"}'
profile = json.loads(text)
```

Think:

JSON STRING -> Python object

Memory trick:

`loads` = load from string


One-table memory aid:

| Function       | Starts with | Result / source |
|----------------|-------------|-----------------|
| `json.dump()`  | Python      | writes to file  |
| `json.dumps()` | Python      | returns string  |
| `json.load()`  | JSON file   | returns Python  |
| `json.loads()` | JSON string | returns Python  |


The repeated-file warning:

This warning from the Python documentation is important:

JSON is not a framed format.

For this level, the practical meaning is:

Do NOT assume I can create one normal JSON file by repeatedly calling `json.dump()` for separate top-level objects one after another.

Bad idea:

```python
with open("data.json", "w", encoding="utf-8") as file:
    json.dump({"name": "Alex"}, file)
    json.dump({"name": "Sam"}, file)
```

This can produce text like:

```text
{"name": "Alex"}{"name": "Sam"}
```

That is not one valid normal JSON document.

Beginner mental model:

One JSON file should contain one complete top-level JSON value.

If I need several related items in that one JSON document, they can belong inside one containing structure such as a list:

```python
profiles = [
    {"name": "Alex"},
    {"name": "Sam"}
]
```

and then that ONE complete structure is dumped.


Learning outcomes for this section:

I should know what JSON is used for at a basic level.

I should understand that JSON can represent nested dictionaries and lists.

I should be able to distinguish `dump`, `dumps`, `load`, and `loads`.

I should know that `dump/load` work with file objects while `dumps/loads` work with strings.

I should understand the direction of conversion: Python to JSON or JSON to Python.

I should understand the repeated-`dump()` warning and why two top-level JSON values written back-to-back do not make one valid normal JSON document.


## `pathlib`: creating and joining paths

What a path is:

A path tells the computer where a file or folder is located.

Example idea:

```text
data/record.json
```

Here:

`data` is a folder

`record.json` is a file inside that folder


Creating a Path object:

`pathlib` is part of Python's standard library.

Import `Path`:

```python
from pathlib import Path
```

Then create a path object:

```python
data_folder = Path("data")
```

Important beginner point:

This creates a Python OBJECT REPRESENTING the path `data`.

It does not automatically create a real folder on the computer.

Another example:

```python
file_path = Path("record.json")
```

Again, this represents a path. It does not itself create the file.


Joining paths with `/`:

`Path` objects let me join path pieces using `/`.

Example:

```python
data_folder = Path("data")
file_path = data_folder / "record.json"
```

`file_path` now represents:

```text
data/record.json
```

Read this as:

start at the `data` path

then go to the child path `record.json`


Joining more than one level:

```python
base = Path("data")
file_path = base / "records" / "record.json"
```

This represents a path such as:

```text
data/records/record.json
```

The useful idea is that I combine path pieces as path objects instead of manually constructing one long path string.


Path object vs actual file:

This is worth repeating because it is an easy confusion:

```python
path = Path("data") / "record.json"
```

only BUILDs a path value in Python.

It does not mean the file definitely exists.

It does not create the file.

It simply gives me a clean path that I can later give to something that works with files.


Learning outcomes for this section:

I should know that a path represents a location of a file or folder.

I should be able to create a `Path` object using `Path(...)`.

I should be able to join child path pieces using `/`.

I should understand that creating a `Path` object does not itself create a real file or directory.

I do NOT need to study the rest of the `pathlib` API for this phase.


## `argparse`: positional arguments, options, and help

What a command-line argument is:

A command-line argument is extra information written after the Python script name when the program is run.

Example command:

```text
python app.py notes.txt
```

Here:

`python` runs Python

`app.py` is the script

`notes.txt` is an argument given to the script

`argparse` helps the program define, read, and explain these arguments.


Starting an `argparse` parser:

```python
import argparse

parser = argparse.ArgumentParser()
```

`ArgumentParser()` creates the object that will understand the command-line arguments my program accepts.


Positional arguments:

A positional argument is identified by WHERE it appears in the command.

Example program:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename")
args = parser.parse_args()

print(args.filename)
```

Run:

```text
python app.py notes.txt
```

`notes.txt` becomes the value of:

```python
args.filename
```

Why is it called positional?

There is no `--filename` written before the value.

The program knows what `notes.txt` means because it appears in the position defined for `filename`.

If a required positional argument is missing, `argparse` reports an error instead of quietly continuing as if the value existed.


What `add_argument()` is doing:

```python
parser.add_argument("filename")
```

tells the parser:

"My program expects a positional argument called `filename`."

Then:

```python
args = parser.parse_args()
```

tells `argparse` to read the actual command the user typed.

After parsing, I access the value with:

```python
args.filename
```


Options:

An option has a name beginning with dashes.

Example:

```python
parser.add_argument("--output")
```

A user could then run:

```text
python app.py notes.txt --output copy.txt
```

The value after `--output` becomes:

```python
args.output
```

Difference to remember:

positional argument:

```text
notes.txt
```

its meaning depends on its position


option:

```text
--output copy.txt
```

its meaning is explicitly named by `--output`


Positional and optional together:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename")
parser.add_argument("--output")
args = parser.parse_args()

print(args.filename)
print(args.output)
```

Command:

```text
python app.py notes.txt --output copy.txt
```

gives me approximately this mental model:

```python
args.filename == "notes.txt"
args.output == "copy.txt"
```

If the optional `--output` is not supplied, its value is normally `None` in this simple form.


Help text:

One major reason to use `argparse` is that it automatically creates command-line help.

If I run:

```text
python app.py --help
```

or:

```text
python app.py -h
```

`argparse` prints usage information and exits.

I do not need to manually create the basic `-h` / `--help` option.


Making help more useful:

I can explain an argument with the `help=` parameter:

```python
parser.add_argument("filename", help="name of the file to use")
parser.add_argument("--output", help="path for the output file")
```

Those descriptions appear in the automatically generated help output.

Mental model:

`add_argument(...)`
defines what input the CLI accepts

`help="..."`
explains that input to the person using the CLI

`parse_args()`
reads the actual arguments supplied when the program runs

`args.some_name`
gives my Python code the parsed value


Learning outcomes for this section:

I should understand what a command-line argument is.

I should know what `ArgumentParser()` is for.

I should know how `add_argument()` defines an accepted argument.

I should understand the difference between a positional argument and an option.

I should know that `parse_args()` reads the arguments the user supplied.

I should know how a parsed value becomes available through `args.<name>`.

I should know that `-h` and `--help` are automatically provided.

I should know how `help=` makes the generated help text understandable.

I do NOT need to study `argparse` features beyond positional arguments, options, and help for this phase.


## `decimal`: exact decimal arithmetic

The problem with normal binary floating-point numbers:

Python's normal `float` uses binary floating-point arithmetic.

Some decimal fractions that look simple to us cannot be represented exactly in binary.

Example:

```python
1.1 + 2.2
```

can produce:

```text
3.3000000000000003
```

This does not mean Python cannot add.

It means the underlying binary floating-point representation cannot represent every decimal fraction exactly.


Why `Decimal` exists:

Python's `decimal` module provides decimal-number arithmetic.

Numbers such as decimal `0.1` can be represented exactly when created correctly as `Decimal` values.

Import:

```python
from decimal import Decimal
```


Creating a Decimal:

Use a STRING for a decimal value:

```python
amount = Decimal("19.99")
```

Another example:

```python
a = Decimal("0.1")
b = Decimal("0.2")
```

Then:

```python
total = a + b
```

gives an exact decimal result:

```python
Decimal('0.3')
```


Why I should not first make a float:

This is an important beginner trap.

Good:

```python
Decimal("0.1")
```

Problematic for exact decimal input:

```python
Decimal(0.1)
```

Why?

In the second version, `0.1` becomes a normal binary `float` FIRST.

That float already contains the binary approximation of 0.1.

`Decimal` then exactly converts THAT approximate float value.

So if my input is supposed to mean the exact decimal number 0.1, create it from the string `"0.1"` rather than from the float `0.1`.


Exact arithmetic example:

With floats:

```python
0.1 + 0.1 + 0.1 - 0.3
```

may not be exactly zero because of binary floating-point representation.

With Decimals created from strings:

```python
Decimal("0.1") + Decimal("0.1") + Decimal("0.1") - Decimal("0.3")
```

gives exact decimal zero.

This exactness is why decimal arithmetic is useful when values must add up exactly rather than approximately.


Basic arithmetic stays familiar:

```python
first = Decimal("10.50")
second = Decimal("2.25")

total = first + second
```

I still use the normal arithmetic operators such as `+`, `-`, `*`, and `/` with Decimal values.

The important change is the NUMBER TYPE being used.


Learning outcomes for this section:

I should understand why normal binary floating point can produce results such as `3.3000000000000003`.

I should know what problem `Decimal` solves.

I should be able to create a Decimal from a string.

I should understand why `Decimal("0.1")` is different from `Decimal(0.1)`.

I should be able to perform basic arithmetic using Decimal values.

I should understand why Decimal is appropriate when decimal totals must use exact stored values.

I do NOT need to study advanced decimal contexts for this phase.


## Required questions

1. Why is a context manager safer than manually closing a file?

Manual version:

```python
file = open("data.txt", "a", encoding="utf-8")
file.write("hello\n")
file.close()
```

The weakness is that closing the file depends on me remembering to call `file.close()` and on program execution actually reaching that line.

Context-manager version:

```python
with open("data.txt", "a", encoding="utf-8") as file:
    file.write("hello\n")
```

`with` controls the lifetime of the opened file.

Python automatically closes it when execution leaves the `with` block, including when an exception interrupts the work inside the block.

Therefore the safer mental model is:

manual `open()` + `close()`
I am responsible for remembering cleanup.

`with open(...)`
Python manages the cleanup for me.

This reduces the chance of accidentally leaving a file open and makes it visually clear which code is allowed to use that file.


2. Why can nested referral data not be represented cleanly in one flat CSV row?

A CSV row is naturally flat.

Example:

```text
id,name,year
1,Alex,2000
```

One column holds one field value in that row.

Nested data is different. It can contain structures inside structures, for example:

```python
{
    "person": {
        "name": "Alex",
        "languages": ["English", "Urdu"]
    },
    "records": [
        {"type": "record A"},
        {"type": "record B"}
    ]
}
```

Here there is:

a dictionary inside a dictionary

a list of languages

a list containing multiple record dictionaries

A single flat CSV row has no natural row-and-column structure for saying "this field contains a list of several structured records".

I could FORCE nested data into a CSV cell by turning it into text, or invent columns such as `record_1`, `record_2`, etc., but then the CSV stops being a clean simple table and becomes awkward when the number of nested items changes.

JSON represents this kind of nesting directly with objects and arrays, so the structure of the stored data can match the structure of the Python dictionaries and lists much more naturally.

Important wording:

This does NOT mean CSV is useless.

CSV is good for flat tabular records.

The problem is trying to cleanly fit variable, nested structures into ONE flat row.


3. Why should services return a result instead of printing it?

First understand the two jobs:

A service does the actual application operation or calculation.

A CLI is the part that communicates with the person using the terminal.

Suppose a function calculates a value.

Printing version:

```python
def calculate_total():
    total = 25
    print(total)
```

The function sends text directly to the terminal.

The caller does not receive `25` as the function's result.

Returning version:

```python
def calculate_total():
    total = 25
    return total
```

Now the caller receives the value:

```python
total = calculate_total()
```

The CLI can decide what to do with it:

```python
print(total)
```

The important separation is:

service:
calculate / validate / perform the operation
return the result

CLI:
decide how that result should be shown to the user

Why this is better:

The returned value can be used by other Python code instead of existing only as terminal text.

Tests can directly check the returned value.

The same service is not tied to one particular way of displaying information.

Core rule to remember:

`return` gives data back to the code that called the function.

`print` only displays text to the output stream.

If the function's job is to produce a useful result for other parts of the program, return that result and let the user-interface layer decide whether and how to print it.


