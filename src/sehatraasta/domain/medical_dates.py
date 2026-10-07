"""Supplied clinical dates, distinct from when an entry was saved."""
from datetime import date
import re


def validate_medical_date(kind, value):
    if kind == 'unknown':
        if value is not None:
            raise ValueError('unknown medical date must have no value')
        return kind, None
    if kind not in ('exact', 'approximate') or not isinstance(value, str):
        raise ValueError('invalid medical date')
    pattern = r'[0-9]{4}-[0-9]{2}-[0-9]{2}' if kind == 'exact' else r'[0-9]{4}(?:-[0-9]{2}(?:-[0-9]{2})?)?'
    if not re.fullmatch(pattern, value):
        raise ValueError('invalid medical date')
    pieces = value.split('-')
    date(int(pieces[0]), int(pieces[1]) if len(pieces) > 1 else 1,
         int(pieces[2]) if len(pieces) > 2 else 1)  # validation only; never save padded precision
    return kind, value


def visit_sort_key(visit):
    """Known supplied dates first; unknown entries grouped by saved order."""
    stamp = visit.creation_time.isoformat()
    return (visit.medical_date_kind == 'unknown', visit.medical_date_value or '',
            0 if visit.medical_date_kind == 'exact' else 1, stamp, visit.ID)
