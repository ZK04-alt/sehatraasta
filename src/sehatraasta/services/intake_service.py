"""Build one complete referral in memory, then persist it exactly once.

Input is ordinary dictionaries of strings, not Flask request objects. Row keys
only link orders/results inside this submission and are never public order IDs.
"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sehatraasta.domain import (Patient, ReferralBundle, MedicationItem, InvestigationOrder,
    DiagnosticResult, ImagingItem, Instruction, CostEntry, Language, ReferralStatus,
    InvestigationOrderStatus, CostCategory)
from sehatraasta.storage.sqlite_repository import amount_to_paisa
from .identifiers import IDAllocator


SECTIONS = ('medications', 'orders', 'results', 'imaging', 'instructions', 'costs')
TEXT = str
SCHEMAS = {
    'patient': {'name': TEXT, 'birth_year': int, 'language': Language},
    'referral': {'creation_time': datetime, 'source_facility': TEXT,
                 'destination': TEXT, 'status': ReferralStatus},
    'medications': {name: TEXT for name in ('name', 'strength', 'dose', 'route',
                    'frequency', 'duration', 'instructions', 'source')},
    'orders': {'name': TEXT, 'date': date, 'source': TEXT, 'workflow_status': InvestigationOrderStatus},
    'results': {'name': TEXT, 'date': date, 'source': TEXT, 'interpretation': TEXT},
    'imaging': {'modality': TEXT, 'body_part': TEXT, 'date': date, 'facility': TEXT, 'report': TEXT},
    'instructions': {'category': TEXT, 'language': Language, 'text': TEXT, 'source': TEXT, 'date': date},
    'costs': {'category': CostCategory, 'amount': Decimal, 'date': date, 'source': TEXT,
              'source_type': TEXT, 'source_identifier': TEXT},
}


OPTIONAL_FIELDS = {
    'patient': {'birth_year'},
    'referral': {'destination', 'source_facility'},
    'medications': {'route', 'instructions', 'source'},
    'orders': {'source'},
    'results': {'source', 'interpretation'},
    'imaging': {'report'},
    'instructions': {'text', 'source'},
    'costs': {'source', 'source_type', 'source_identifier'},
}


class IntakeError(ValueError):
    def __init__(self, issues):
        super().__init__('invalid referral intake')
        self.issues = issues


def issue(section, row_index, field, code):
    return dict(section=section, row_index=row_index, field=field, code=code)


def parse_values(section, index, values, issues):
    parsed = {}
    for field, kind in SCHEMAS[section].items():
        value = values.get(field, '')
        if isinstance(value, str) and not value.strip() and field in OPTIONAL_FIELDS.get(section, set()):
            parsed[field] = None if section == 'patient' and field == 'birth_year' else ''
            continue
        if not isinstance(value, str) or not value.strip():
            issues.append(issue(section, index, field, 'error.required'))
            continue
        try:
            if kind in (date, datetime):
                parsed[field] = kind.fromisoformat(value)
            elif kind in (str, int, Decimal):
                parsed[field] = kind(value)
            else:
                parsed[field] = kind[value]
        except (ValueError, KeyError, InvalidOperation, OverflowError):
            code = 'error.date' if kind in (date, datetime) else 'error.choice' if kind not in (str, int, Decimal) else 'error.invalid'
            issues.append(issue(section, index, field, code))
    return parsed


def domain_issue(section, index, error):
    message = str(error).lower()
    field = None
    # Only developer-owned names and stable codes leave the service.
    for candidate in sorted(SCHEMAS[section], key=len, reverse=True):
        if candidate.replace('_', ' ') in message:
            field = candidate
            break
    if 'birth year' in message:
        field = 'birth_year'
    if 'order status' in message:
        field = 'workflow_status'
    code = 'error.required' if message.startswith('missing') else 'error.invalid'
    if 'amount' in message or 'paisa' in message:
        field, code = 'amount', 'error.amount'
    elif 'date' in message or 'time' in message:
        code = 'error.date'
    elif 'unknown' in message or 'unsupported' in message:
        code = 'error.choice'
    return issue(section, index, field, code)


class IntakeService:
    def __init__(self, repository):
        self.repository = repository

    def create(self, data, unfinished=None):
        issues = []
        mode = data.get('mode')
        if mode not in ('new', 'existing'):
            issues.append(issue('patient', None, 'mode', 'error.choice'))
        allocator = IDAllocator(self.repository)
        patient = None
        if mode == 'existing':
            patient = self.repository.get_patient(data.get('patient_id', ''))
            if patient is None:
                issues.append(issue('patient', None, 'patient_id', 'error.not_found'))
            else:
                patient = deepcopy(patient)
        elif mode == 'new':
            values = parse_values('patient', None, data.get('patient', {}), issues)
            if len(values) == len(SCHEMAS['patient']):
                try:
                    patient = Patient(allocator.allocate('patient'), **values)
                    if patient.birth_year is not None and patient.birth_year > 9223372036854775807:
                        raise ValueError('invalid birth year')
                except ValueError as error:
                    issues.append(domain_issue('patient', None, error))
        values = parse_values('referral', None, data.get('referral', {}), issues)
        bundle = None
        if len(values) == len(SCHEMAS['referral']):
            try:
                from sehatraasta.domain.medical_dates import validate_medical_date
                raw = data.get('referral',{})
                kind,value = validate_medical_date(raw.get('medical_date_kind') or 'unknown',raw.get('medical_date_value') or None)
                bundle = ReferralBundle(allocator.allocate('bundle'), **values,medical_date_kind=kind,medical_date_value=value)
            except ValueError as error:
                issues.append(domain_issue('referral', None, error))

        records = {section: [] for section in SECTIONS}
        orders = {}
        for section in SECTIONS:
            rows = data.get(section, [])
            for row in rows:
                index = row['_key']
                if not any(str(value).strip() for key, value in row.items() if key != '_key'):
                    continue
                values = parse_values(section, index, row, issues)
                if len(values) != len(SCHEMAS[section]):
                    continue
                try:
                    if section == 'medications':
                        item = MedicationItem(ID=allocator.allocate('medication'), **values)
                    elif section == 'orders':
                        item = InvestigationOrder(**values)
                        orders[str(index)] = item
                    elif section == 'results':
                        order_key = row.get('order_key', '')
                        if order_key and order_key not in orders:
                            issues.append(issue(section, index, 'order_key', 'error.choice'))
                            continue
                        item = DiagnosticResult(ID=allocator.allocate('result'),
                                                investigation_order=orders.get(order_key), **values)
                    elif section == 'imaging':
                        item = ImagingItem(ID=allocator.allocate('imaging'), Attachment_ID=None, **values)
                    elif section == 'instructions':
                        item = Instruction(**values)
                    else:
                        item = CostEntry(ID=allocator.allocate('cost'), note=row.get('note', ''), **values)
                        amount_to_paisa(item.amount)  # Validate storage range/precision before any write.
                    records[section].append(item)
                except ValueError as error:
                    issues.append(domain_issue(section, index, error))
        if issues:
            raise IntakeError(issues)
        bundle.medication_item = records['medications']
        bundle.investigation_orders = records['orders']
        bundle.diagnostic_results = records['results']
        bundle.imaging_items = records['imaging']
        bundle.instructions = records['instructions']
        bundle.cost_entries = records['costs']
        bundle.checks()
        patient.add_referral(bundle)
        patient.checks()
        # SQLiteRepository._save owns BEGIN IMMEDIATE, commit, rollback and revision checks.
        # Never call the public add-record services here: each would commit separately.
        try:
            if unfinished is not None:
                self.repository.complete_intake(patient, mode == 'new', unfinished)
            elif mode == 'new':
                self.repository.add_patient(patient)
            else:
                self.repository.save_patient(patient)
        except ValueError as error:
            code = 'visit.save_conflict' if unfinished is not None and str(error) == 'unfinished visit changed; reopen before saving' else 'error.duplicate'
            raise IntakeError([issue('form', None, None, code)]) from None
        return bundle
