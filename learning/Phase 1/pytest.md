> Personal learning notes kept for Zunair Ali Khan to learn. These are separate from the app and its release evidence.

# Unit Tests

**Unit testing** means writing code that tests individual parts of your program, usually functions.

Instead of manually running a program with different inputs each time, you can create tests that automatically check whether functions return the expected results.

Example function:

```python
def square(n):
    return n * n
```

A separate test file can import the function:

```python
from calculator import square
```

---

## `assert`

`assert` checks whether a condition is `True`.

Syntax:

```python
assert condition
```

Example:

```python
assert square(2) == 4
assert square(3) == 9
```

If the condition is **true**, nothing happens.

If the condition is **false**, Python raises an:

```text
AssertionError
```

Example:

```python
def square(n):
    return n + n
```

Now:

```python
assert square(3) == 9
```

fails because:

```text
square(3) = 6
```

instead of `9`.

---

## `pytest`

`pytest` is a third-party library used to automatically run unit tests.

Install it with:

```bash
pip install pytest
```

A test file might look like:

```python
from calculator import square #calculator is file name and square is function name


def test_square():
    assert square(2) == 4
    assert square(3) == 9
    assert square(-2) == 4
    assert square(-3) == 9
    assert square(0) == 0
```

Run the tests with:

```bash
pytest test_calculator.py
```

`pytest` runs the tests and reports which ones passed or failed.

---

## pytest Discovery

`pytest` automatically discovers test functions based on their names.

Test functions should start with:

```text
test_
```

Example:

```python
def test_square():
    ...
```

You therefore do **not** need to manually call:

```python
test_square()
```

---

## Test Categories

Instead of putting every test inside one function, divide tests into categories.

Example:

```python
from calculator import square


def test_positive():
    assert square(2) == 4
    assert square(3) == 9


def test_negative():
    assert square(-2) == 4
    assert square(-3) == 9


def test_zero():
    assert square(0) == 0
```

This makes it easier to see **which type of input is causing the problem**.

---

## Testing Exceptions

Sometimes the correct behaviour of a function is to raise an exception.

`pytest` can test whether the expected exception occurs.

First import `pytest`:

```python
import pytest
```

Syntax:

```python
with pytest.raises(ExceptionType):
    function()
```

Example:

```python
def test_str():
    with pytest.raises(TypeError):
        square("cat")
```

This test is saying:

> Calling `square("cat")` should raise a `TypeError`.

If `TypeError` is raised, the test **passes**.

If the expected exception is not raised, the test **fails**.

---

## Complete Example

### `calculator.py`

```python
def square(n):
    return n * n
```

### `test_calculator.py`

```python
import pytest

from calculator import square


def test_positive():
    assert square(2) == 4
    assert square(3) == 9


def test_negative():
    assert square(-2) == 4
    assert square(-3) == 9


def test_zero():
    assert square(0) == 0


def test_str():
    with pytest.raises(TypeError):
        square("cat")
```

---
