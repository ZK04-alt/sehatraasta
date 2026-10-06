"""HTTP field descriptions and conversion only; domain rules remain in services."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum

from sehatraasta.domain import (Language, ReferralStatus, InvestigationOrderStatus,
    CostCategory, ReviewCategory, PresenceState, AttachmentCategory, ProvenanceType)


def field(name, label=None, kind='text', required=True, choices=None, convert=None):
    if kind == 'checkbox':
        convert = checked
    return dict(name=name, label='field.' + (label or name), kind=kind,
                required=required, choices=choices, convert=convert)


def checked(value):
    if value != 'yes':
        raise ValueError('confirmation required')
    return True


ID = field('ID', 'id')
SOURCE = field('source', kind='textarea', required=False)
DAY = field('date', kind='date', convert=date.fromisoformat)
TIME = field('time', kind='datetime-local', convert=datetime.fromisoformat)


def enum_field(name, enum, label=None):
    return field(name, label, 'select', choices=[(item.name, item.name.lower().replace('_', ' ')) for item in enum], convert=lambda value: enum[value])


def preset(name, options, required=True):
    return field(name, kind='preset', required=required,
                 choices=[(value, value) for value in options])


def submitted_value(item, values, name=None):
    name = name or item['name']
    value = values.get(name, '')
    if item['kind'] == 'preset' and value == '__custom__':
        return values.get(name + '__custom', '')
    return value


FORMS = {
    'patient': [ID, field('name'), field('birth_year', kind='year', convert=int), enum_field('language', Language)],
    'bundle': [field('patient_id', 'patient', 'select', choices=[]), field('creation_time', 'created', 'datetime-local', convert=datetime.fromisoformat),
               field('source_facility', 'facility'), field('destination', required=False)],
    'edit': [field('source_facility', 'facility'), field('destination', required=False)],
    'medication': [ID, field('name'),
                   preset('strength', ['5 mg', '10 mg', '20 mg', '50 mg', '100 mg', '250 mg', '500 mg', '1 g']),
                   preset('dose', ['1 tablet', '2 tablets', '1 capsule', '5 mL', '10 mL']),
                   preset('route', ['By mouth', 'On the skin', 'Inhaled', 'Eye drops', 'Ear drops', 'Nasal'], False),
                   preset('frequency', ['Once a day', 'Twice a day', 'Three times a day', 'At bedtime', 'As needed']),
                   preset('duration', ['3 days', '5 days', '7 days', '10 days', '14 days', 'As directed']),
                   field('instructions', kind='textarea', required=False), SOURCE],
    'order': [field('name'), DAY, SOURCE, enum_field('workflow_status', InvestigationOrderStatus, 'status')],
    'result': [ID, field('name'), DAY, SOURCE, field('interpretation', kind='textarea', required=False), field('order_name', 'link', required=False)],
    'imaging': [ID, preset('modality', ['X-ray', 'Ultrasound', 'CT scan', 'MRI', 'Mammogram']), field('body_part'), DAY, field('facility'), field('report', kind='textarea', required=False), field('attachment_id', 'link', required=False)],
    'instruction': [field('category'), enum_field('language', Language), field('text', kind='textarea', required=False), SOURCE, DAY],
    'cost': [ID, enum_field('category', CostCategory), field('amount', convert=Decimal), DAY, SOURCE,
             field('source_type', required=False), field('source_identifier', 'reference', required=False), field('note', kind='textarea', required=False)],
    'review': [enum_field('category', ReviewCategory), enum_field('state', PresenceState, 'status'),
               field('text', 'reviewer'), TIME, field('note', kind='textarea')],
    'attachment': [ID, field('file', kind='file'), enum_field('category', AttachmentCategory), DAY,
                   enum_field('source_type', ProvenanceType), field('source', kind='textarea', required=False),
                   field('source_identifier', 'reference', required=False), field('link', 'link', 'select', False, [])],
    'lookup': [field('payload')],
    'restore': [field('archive', kind='file')],
    'delete': [field('confirm', 'delete_confirm', 'checkbox')],
    'backup': [field('confirm', 'backup_confirm', 'checkbox')],
    'context': [field('medical_history', kind='textarea', required=False), field('allergies', kind='textarea', required=False),
        field('referral_reason', kind='textarea', required=False), field('referral_notes', kind='textarea', required=False),
        field('department', required=False), field('follow_up_date', kind='date', required=False, convert=date.fromisoformat), SOURCE],
}

# Public entry forms never ask users to allocate record identifiers.
for name in ('patient', 'medication', 'result', 'imaging', 'cost', 'attachment'):
    FORMS[name] = [item for item in FORMS[name] if item['name'] != 'ID']

# Display labels do not rename stored fields or change existing records.
LABELS = {
    'patient': {'name': 'patient_name'},
    'medication': {'name': 'medicine_name'},
    'order': {'name': 'test_name', 'workflow_status': 'test_status'},
    'result': {'name': 'test_name', 'order_name': 'linked_test'},
    'cost': {'category': 'expense_type'},
    'attachment': {'category': 'document_type'},
    'instruction': {'category': 'instruction_type'},
    'review': {'category': 'review_type', 'state': 'availability'},
    'bundle': {'source_facility': 'sending_facility'},
    'edit': {'source_facility': 'sending_facility'},
}
HINTS = {'birth_year': 'year', 'destination': 'destination', 'status': 'referral_status',
         'strength': 'strength', 'dose': 'dose', 'source': 'source',
         'source_type': 'source_type', 'source_identifier': 'source_reference'}
for kind, items in FORMS.items():
    for item in items:
        if item['name'] in LABELS.get(kind, {}):
            item['label'] = 'field.' + LABELS[kind][item['name']]
        if item['name'] in HINTS:
            item['hint'] = 'help.' + HINTS[item['name']]
        if kind == 'attachment' and item['name'] == 'source_type':
            item['required'] = False
            item['default'] = ProvenanceType.NOT_SUPPLIED


def convert_form(fields, values, files):
    parsed, errors = {}, []
    for item in fields:
        name = item['name']
        value = files.get(name) if item['kind'] == 'file' else submitted_value(item, values)
        empty = not value or (isinstance(value, str) and not value.strip())
        if empty and item['required']:
            errors.append({'field': name, 'code': 'error.required'})
            continue
        if empty:
            parsed[name] = item.get('default', None if name in ('link', 'order_name', 'attachment_id') else '')
            continue
        try:
            parsed[name] = item['convert'](value) if item['convert'] else value
        except (ValueError, TypeError, KeyError, InvalidOperation):
            code = 'error.date' if item['kind'] in ('date', 'datetime-local') else 'error.choice' if item['choices'] else 'error.invalid'
            errors.append({'field': name, 'code': code})
    return parsed, errors


def display_value(value):
    if isinstance(value, Enum):
        return value.value if isinstance(value.value, str) else value.name
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value) if value is not None and value != '' else None
