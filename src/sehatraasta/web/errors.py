"""Framework-neutral adapter for the future Flask error handler.

No Flask route is built in Phase 6. A future handler can pass this dictionary
to its template and use the returned HTTP status.
"""
from sehatraasta.presentation.errors import error_from_exception


def error_response(error, language="en", field=None):
    presented = error_from_exception(error, field)
    return presented.to_dict(language), presented.status
