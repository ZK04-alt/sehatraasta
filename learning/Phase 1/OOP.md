> Personal learning notes kept for Zunair Ali Khan to learn. These are separate from the app and its release evidence.

# Object-Oriented Programming

## Create Custom Data Types

### Classes

Syntax:

```python
class *class name*:
    def __init__(self, name, house):
        self.name = name
        self.house = house

        # this function can include error checking

    def __str__(self):
        return *string*
```

`__str__` is printed whenever you do:

```python
print(*class name*)
```

Methods are functions inside classes.

---

## Using a Class

```python
variable = *class name*()
```

This creates an **object** of the class.

You can then assign values to attributes:

```python
variable.attribute = attribute value
```

Example:

```python
student = Student()
student.name = "harry"
```

---

## Passing Values Into Classes

Pass values into classes like you would with functions, allowing the class to act on those values before passing them to a variable.

Example:

```python
name = "harry"
house = "griffindor"

student = Student(name, house)
```

---

## Custom Methods

```python
def function_name(self):
```

Custom methods can use the `self.variables` variables from `__init__`.
