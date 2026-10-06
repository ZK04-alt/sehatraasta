Resources:

1. [Flask application factory](https://flask.palletsprojects.com/en/stable/tutorial/factory/)
   - Creating and configuring the application.
2. [Flask views and blueprints](https://flask.palletsprojects.com/en/stable/tutorial/views/)
   - Requests, form values, redirects and groups of routes.
3. [Flask templates](https://flask.palletsprojects.com/en/stable/tutorial/templates/)
   - Jinja expressions, loops, inheritance and escaping.
4. [Flask static files](https://flask.palletsprojects.com/en/stable/tutorial/static/)
   - Local CSS and JavaScript.
5. [Flask testing](https://flask.palletsprojects.com/en/stable/testing/)
   - Testing requests without opening a browser.
6. [Flask security considerations](https://flask.palletsprojects.com/en/stable/web-security/)
   - Form protection, request limits and safe HTML.

Date prepared: 21-Sep-2026

Reading and personal explanation still need to be done. This is not a record of completed study.

notes:

## Flask, the browser and HTTP

Flask:

Flask connects a browser request to a Python function.
That function prepares a response.

HTTP:

HTTP is the request/response protocol between the browser and the local server.
It still works when both run on the same computer.

Important mental model:

The browser displays HTML. It does not directly run the Python classes.

Example sequence:

1. The browser requests a page.
2. Flask chooses the matching route.
3. The route calls a service.
4. The service supplies records.
5. A template turns those records into HTML.
6. The browser displays the HTML.

The program still needs the existing domain, services and storage layers.

## An application factory

A factory is a function that creates and returns an application object.

Small example:

```python
from flask import Flask

def create_app():
    app = Flask(__name__)
    return app
```

Break this down:

`Flask(__name__)`
creates the application and gives Flask the module's location context.

`app =`
keeps that application object in a variable.

`return app`
passes the object back to the caller.

This example only creates the application. It does not define a page yet.

Why a function helps:

A test can create a separate application with a temporary database.
That keeps test data away from the working database.

## Routes and blueprints

A route connects an address and an HTTP method to a function.
A blueprint groups related routes before the factory registers them.

Small example:

```python
from flask import Blueprint

pages = Blueprint("pages", __name__)

@pages.get("/hello")
def hello():
    return "Hello"
```

Break this down:

`Blueprint("pages", __name__)`
creates a group named `pages`.

`@pages.get("/hello")`
connects GET requests for `/hello` to the next function.

`hello()`
returns the response content.

The factory must register the blueprint before the route becomes available.
The decorator does not immediately run the function.

## GET, POST and submitted text

GET normally requests a page.
POST submits information for an action.

Submitted form values usually arrive as text, even when they represent numbers.

Example:

```python
year_text = request.form.get("birth_year", "")
```

`request.form`
contains submitted fields.

`get("birth_year", "")`
reads that field, with an empty string as the fallback.

The route must convert text when needed. Conversion can fail.
The existing domain checks still decide whether a converted value is valid.

Important trap:

A dropdown or a `required` attribute is not a security boundary.
A request can bypass the browser form.

## Services and routes have different jobs

The route understands HTTP, form fields, redirects and response codes.
The service understands an application action.
The repository understands storage.

For example, the route asks the service to add a cost.
It does not write SQL or calculate a second version of the total.

This avoids different business rules in the CLI and website.

## Jinja templates

A template contains HTML and placeholders for values.
Jinja fills those placeholders on the server.

Example:

```html
<h1>{{ heading }}</h1>
{% for title in titles %}
  <p>{{ title }}</p>
{% endfor %}
```

Break this down:

`{{ heading }}`
inserts a value into the output.

`{% for title in titles %}`
starts a loop.

`{% endfor %}`
ends the loop.

`{{ ... }}` displays a value. `{% ... %}` controls template behaviour.

A base template contains shared navigation and page structure.
Other templates extend it and fill a content block.

Important trap:

HTML templates escape inserted text by default.
Do not add `|safe` to source text just to make it look different.
Text resembling HTML must remain text, not active markup.

## Redirects and response codes

After a successful save, the program returns a redirect.
The browser then requests the destination page with GET.

This is called Post/Redirect/Get.
It reduces accidental repeat submissions when the page is refreshed.
It does not replace duplicate checks.

Codes used in the website:

| Code | Meaning here |
| --- | --- |
| 200 | Page or download returned |
| 303 | Save succeeded; request another page with GET |
| 400 | Form protection failed or expired |
| 403 | Request came from a rejected origin or address |
| 404 | Page, record or file was not found |
| 409 | Duplicate record or repeated submission |
| 413 | Request exceeds the size limit |
| 422 | Submitted data needs correction |
| 500 | Unexpected failure |
| 503 | Storage is unavailable |

An error page must never claim that a save succeeded.

## CSS, JavaScript and static files

Static files are served without Jinja rendering.
CSS controls layout and appearance.
JavaScript adds small browser interactions.

The program uses local files for both.
No external font or icon server is required.

The JavaScript moves focus to the error summary, shows submission feedback and opens the print dialog.
The main forms still work without JavaScript.

## Form protection and private information

CSRF means cross-site request forgery.
It describes an unwanted request triggered from another site.

The form includes a signed, time-limited token.
The program checks its session, route and expiry before accepting a POST.
A successful write consumes that token.

A signature detects tampering. It does not encrypt the contents.

Important trap:

A signed session cookie is not a login.
The program must not place patient records in it.
Loopback access does not make local files encrypted or protected from other device users.

The normal launch command disables debug mode.
Errors show safe messages rather than private values or stack traces.

## Labels, errors and language

Each input needs a visible label.
The label's `for` value matches the input's `id`.

An error summary links to the invalid input.
The input also has an inline error message.
Keyboard focus must stay visible.

`dir="rtl"` sets right-to-left page direction.
It does not reverse a stored string.
IDs and dates need isolated left-to-right presentation.

Interface wording may change language. Original source wording stays unchanged.
Draft translations still need a human reviewer.

## Route tests and browser tests

A Flask test client sends requests without opening a browser.

Small example, assuming `app` is a configured test fixture:

```python
def test_missing_page(app):
    response = app.test_client().get("/unknown-page")
    assert response.status_code == 404
```

Break this down:

`app.test_client()`
creates the request client.

`.get(...)`
sends the request.

`response.status_code`
contains the response code.

A passing route test does not prove that keyboard navigation or printing works.
Those need browser checks as well.

## What I should be able to explain

- The path from a browser request to a service and back to HTML.
- Why the route does not contain SQL or duplicate cost rules.
- The difference between GET, POST and a redirect.
- The difference between a Jinja value and a Jinja loop.
- Why source text stays escaped.
- Why a signed token is not encryption or authentication.
- Why a passing route test is not a complete accessibility review.

## Common mistakes to avoid

- Saving on a normal GET request.
- Trusting browser validation alone.
- Putting source records into cookies or logs.
- Copying business rules into templates.
- Showing success before the service confirms the action.
- Treating an empty review group as missing medical information.
- Assuming a translation is reviewed because the page renders correctly.
