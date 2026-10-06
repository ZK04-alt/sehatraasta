# Modules, Data Classes, Enums, Exceptions & Testing

## Modules

A **module** is a Python file containing functions, classes, variables, or other Python code.

Example:

```text
referral.py
```

is a module called:

```python
referral
```

---

## Importing Modules

Import the whole module:

```python
import referral
```

Then access things inside it using:

```python
referral.create_referral()
```

Import something specific:

```python
from referral import create_referral
```

Then use it directly:

```python
create_referral()
```

You can also rename an import:

```python
import referral as ref
```

### Avoid

```python
from referral import *
```

This imports many names without making it clear where they came from and can cause naming conflicts.

---

## One Module = One Clear Responsibility

As a program gets bigger, split it into modules based on what each part is responsible for.

Example:

```text
project/
    main.py
    models.py
    referral.py
    exceptions.py
```

Possible responsibilities:

```text
main.py
    user input and output

models.py
    data classes and enums

referral.py
    referral-related functions and rules

exceptions.py
    custom exceptions
```

### Main idea

A module should have **one clear responsibility**.

Do not put unrelated parts of the whole program into one large `.py` file.

---

## Packages

A **package** is a directory containing multiple related Python modules.

Example:

```text
project/
    __init__.py
    models.py
    referral.py
    exceptions.py
```

You can import modules from a package:

```python
from project.referral import create_referral
```

Packages let larger programs organise related modules together.

`__init__.py` can be an empty file for a simple package.

---

# Separating Program Logic From Input/Output

## Input/Output Belongs at the Edge

Core program logic should generally not be responsible for asking the user questions or printing results.

Instead:

```text
input
   ↓
main.py
   ↓
domain function
   ↓
return value OR exception
   ↓
main.py
   ↓
output
```

### Avoid

```python
def create_referral():
    name = input("Name: ")

    if name == "":
        print("Invalid name")
        return

    print("Referral created")
```

The function is doing:

- input
- validation
- program logic
- output

all at once.

### Prefer

Domain function:

```python
def create_referral(name):
    if name == "":
        raise InvalidReferralError("Name cannot be empty")

    return name
```

Input/output code:

```python
name = input("Name: ")

try:
    referral = create_referral(name)
    print(referral)
except InvalidReferralError as error:
    print(error)
```

The domain function:

```text
accepts values
      ↓
performs its job
      ↓
returns a value
OR
raises a specific exception
```

It does not need to know whether its input came from:

- the terminal
- a web form
- a test
- another function

This makes the function easier to reuse and test.

---

# Data Classes

A **data class** is useful for classes whose main purpose is storing related data.

Import:

```python
from dataclasses import dataclass
```

Syntax:

```python
@dataclass
class Student:
    name: str
    house: str
```

Create an object:

```python
student = Student("Harry", "Gryffindor")
```

This automatically gives the class an `__init__()` similar to:

```python
def __init__(self, name, house):
    self.name = name
    self.house = house
```

So you do not have to manually write it.

---

## Generated Methods

By default, `@dataclass` can automatically create useful methods including:

```text
__init__()
__repr__()
__eq__()
```

### `__init__`

Allows:

```python
student = Student("Harry", "Gryffindor")
```

### `__repr__`

Provides a useful representation of the object.

Example:

```python
print(student)
```

can produce something similar to:

```text
Student(name='Harry', house='Gryffindor')
```

### `__eq__`

Allows objects of the same data class to be compared using their fields.

Example:

```python
student1 = Student("Harry", "Gryffindor")
student2 = Student("Harry", "Gryffindor")

student1 == student2
```

Result:

```python
True
```

because their fields contain the same values.

---

# Data Class Fields

Each annotated variable inside a data class is a **field**.

Example:

```python
@dataclass
class Student:
    name: str
    house: str
```

Fields:

```text
name
house
```

Fields can have default values:

```python
@dataclass
class Student:
    name: str
    house: str = "Unknown"
```

Now this is valid:

```python
student = Student("Harry")
```

and:

```python
student.house
```

is:

```text
Unknown
```

---

## `field()`

Use `field()` when a field needs extra configuration.

Import:

```python
from dataclasses import dataclass, field
```

A common use is creating default lists.

```python
@dataclass
class Referral:
    name: str
    attachments: list = field(default_factory=list)
```

Now:

```python
referral = Referral("Example")
```

automatically gets its own empty list:

```python
referral.attachments
```

```text
[]
```

### Why `default_factory`

For mutable values such as:

```text
list
dict
set
```

use a factory to create a **new object for each instance**.

Example:

```python
attachments: list = field(default_factory=list)
```

---

# Frozen Data Classes

Normally, fields can be changed after creating the object.

```python
@dataclass
class Student:
    name: str
```

```python
student = Student("Harry")
student.name = "Ron"
```

This is allowed.

---

Use:

```python
@dataclass(frozen=True)
class Student:
    name: str
```

Now:

```python
student = Student("Harry")
student.name = "Ron"
```

raises a:

```text
FrozenInstanceError
```

`frozen=True` therefore makes the data class behave like its fields are read-only after creation.

### Important

It **emulates immutability**. It does not make every possible object contained inside the data class completely immutable.

---

# Data Classes Are Not Database Tables

A data class represents data **inside Python**.

Example:

```python
@dataclass
class Referral:
    patient_name: str
    status: str
```

This creates a Python class.

It does **not** automatically:

- create a SQLite table
- save objects
- load objects
- generate IDs
- update a database
- delete database records

Those are separate database responsibilities.

Think of it as:

```text
Data class
    = how data is represented in Python

Database table
    = how data is stored permanently
```

They may represent similar information, but one does not automatically create the other.

---

# Enums

An **enum** provides a fixed set of allowed named values.

Import:

```python
from enum import Enum
```

Example:

```python
class Status(Enum):
    PRESENT = "present"
    MISSING = "missing"
    PENDING = "pending"
    NOT_APPLICABLE = "not applicable"
```

Use:

```python
status = Status.PRESENT
```

An enum member has a name:

```python
status.name
```

```text
PRESENT
```

and a value:

```python
status.value
```

```text
present
```

---

## Why Use an Enum for Status

Without an enum:

```python
status = "present"
```

different parts of the program could accidentally use:

```text
"Present"
"present"
"PRESENT"
"available"
"presnt"
```

These are all different strings.

This causes **free-text status drift**.

With an enum:

```python
Status.PRESENT
Status.MISSING
Status.PENDING
Status.NOT_APPLICABLE
```

the program has one controlled set of status values.

### Main idea

Use an enum when a value should only come from a **fixed set of valid choices**.

---

# Exceptions

Exceptions represent errors or unusual situations that interrupt normal program execution.

Examples:

```text
ValueError
TypeError
FileNotFoundError
```

---

## Handling Exceptions

Use:

```python
try:
    # code that may raise an exception

except ExceptionType:
    # what to do if that exception happens
```

Example:

```python
try:
    age = int(input("Age: "))
except ValueError:
    print("Age must be a number")
```

Python first runs the `try` block.

If no exception occurs:

```text
except is skipped
```

If the matching exception occurs:

```text
remaining try code is skipped
        ↓
matching except block runs
```

---

## Catch Specific Exceptions

Prefer:

```python
except ValueError:
```

when you know which error you expect.

This makes it clearer what problem your code is handling.

---

# Raising Exceptions

Your own functions can deliberately raise exceptions when something is invalid.

Syntax:

```python
raise ExceptionType("message")
```

Example:

```python
def set_age(age):
    if age < 0:
        raise ValueError("Age cannot be negative")

    return age
```

Calling:

```python
set_age(-5)
```

raises:

```text
ValueError: Age cannot be negative
```

---

# Custom Exceptions

You can create exceptions specifically for your program.

Syntax:

```python
class InvalidReferralError(Exception):
    pass
```

Then raise it:

```python
def create_referral(name):
    if name == "":
        raise InvalidReferralError("Referral must have a name")

    return name
```

Handle it:

```python
try:
    referral = create_referral("")
except InvalidReferralError as error:
    print(error)
```

Custom exception names normally end with:

```text
Error
```

---

## Why Use Specific Custom Exceptions

Instead of a function doing this:

```python
def create_referral(name):
    if name == "":
        return None
```

it can communicate exactly what went wrong:

```python
def create_referral(name):
    if name == "":
        raise InvalidReferralError("Referral must have a name")

    return name
```

The caller can then decide what to do.

For example:

```text
CLI
    → print an error

web app
    → display an error message

test
    → check that the correct exception occurs
```

The domain function itself does not need to handle the user interface.

---

# Domain Functions

A **domain function** contains the actual rules or logic of the program.

General pattern:

```python
def domain_function(value):
    if value is invalid:
        raise SpecificError()

    return result
```

A domain function should normally:

```text
receive values
perform logic
return values
raise specific exceptions when something is invalid
```

rather than directly doing:

```text
input()
print()
```

---

# Where Exceptions Should Be Handled

A useful structure is:

```text
main.py / web route
        ↓
collect input
        ↓
domain function
        ↓
returns result
        OR
raises exception
        ↓
main.py / web route handles it
        ↓
show output to user
```

Example:

```python
def create_referral(name):
    if not name:
        raise InvalidReferralError("Name is required")

    return name
```

Then at the edge:

```python
name = input("Name: ")

try:
    result = create_referral(name)
    print(result)
except InvalidReferralError as error:
    print(error)
```

---

# Testing: Fail for the Expected Reason

A failing test is useful only when it fails because of the behaviour the test was designed to check.

For example, suppose you are testing:

```text
invalid status should raise InvalidStatusError
```

You want the test to fail if:

```text
InvalidStatusError is not raised
```

You do **not** want it to fail because:

```text
the function name is misspelled
an import is broken
an unrelated variable does not exist
the test itself contains an error
```

### Main idea

When a test fails, read the failure output and check:

```text
Did the behaviour I was testing fail?
```

not simply:

```text
Did pytest show red?
```

A red test caused by an unrelated error does not prove that your test is correctly checking the intended behaviour.

---

# How These Ideas Fit Together

Example project:

```text
project/
    main.py
    models.py
    referral.py
    exceptions.py
    tests/
        test_referral.py
```

### `models.py`

Contains data representations:

```text
data classes
enums
```

### `referral.py`

Contains domain logic:

```text
functions accept values
functions return values
functions raise specific exceptions
```

### `exceptions.py`

Contains custom exceptions:

```text
InvalidReferralError
InvalidStatusError
```

### `main.py`

Contains input/output:

```text
input()
print()
exception handling for the user
```

### `tests/`

Checks domain behaviour:

```text
valid inputs return expected values
invalid inputs raise expected exceptions
```

---

# Takeaways

- A **module** is a `.py` file containing Python code.
- Split larger programs into modules with clear responsibilities.
- A **package** groups related modules together.
- Keep input/output at the **edge** of the program.
- Domain functions should accept values and either **return values or raise specific exceptions**.
- `@dataclass` automatically generates useful methods such as `__init__`, `__repr__`, and `__eq__`.
- Data class variables with type annotations become **fields**.
- `field(default_factory=...)` is useful for mutable defaults such as lists.
- `frozen=True` prevents normal reassignment of data class fields.
- A data class represents Python data; it does **not** automatically become a database table.
- An **enum** gives you a controlled set of valid values.
- Enums help prevent free-text values such as statuses from becoming inconsistent.
- `try` / `except` handles expected exceptions.
- `raise` deliberately signals that something has gone wrong.
- Custom exceptions allow your program to represent specific types of errors.
- A failing test should fail because of the **exact behaviour being tested**, not an unrelated problem.
