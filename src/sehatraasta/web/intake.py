"""HTTP adaptation and display state for combined intake; no persistence rules."""
from datetime import date, datetime
import re

from flask import current_app, g, request, render_template, redirect, flash
from werkzeug.datastructures import MultiDict

from sehatraasta.services.intake_service import IntakeService, IntakeError, SECTIONS, issue
from sehatraasta.storage.errors import StorageError, log_storage_error
from .forms import FORMS, field, submitted_value
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService

KINDS = dict(zip(SECTIONS, ('medication', 'order', 'result', 'imaging', 'instruction', 'cost')))


def section_fields(section):
    items = [dict(item) for item in FORMS[KINDS[section]]
             if item['name'] not in ('order_name', 'attachment_id')]
    if section == 'results':
        items.append(field('order_key', 'intake_order', 'select', False, []))
    return items


def read_submission(form=None):
    form = request.form if form is None else form
    values = form.to_dict()
    data = dict(mode=values.get('mode', ''), patient_id=values.get('patient_id', ''),
                patient={item['name']: values.get(item['name'], '') for item in FORMS['patient']},
                referral={item['name']: values.get(item['name'], '') for item in FORMS['bundle'][1:]})
    data['referral']['status'] = 'DRAFT'
    rows, issues = {}, []
    for section in SECTIONS:
        rows[section] = []
        data[section] = []
        for key in form.getlist(section + '.rows'):
            if not key.isascii() or not key.isdecimal() or len(key) > 7 or str(int(key)) != key or key in rows[section]:
                issues.append(issue('form', None, None, 'error.form'))
                continue
            rows[section].append(key)
            row = {'_key': int(key)}
            for item in section_fields(section):
                row[item['name']] = submitted_value(item, values, section + '.' + key + '.' + item['name'])
                # A selected Custom control starts a row even before text is entered.
                if values.get(section + '.' + key + '.' + item['name']) == '__custom__':
                    row['_started'] = 'yes'
            data[section].append(row)
    return values, rows, data, issues


def display_fields(items, prefix='', values=None):
    result = []
    for item in items:
        displayed = dict(item)
        displayed['name'] = prefix + item['name']
        displayed['control_id'] = displayed['name'].replace('.', '-')
        # Repeated rows and patient modes have conditional requirements on the server.
        displayed['conditional'] = True
        raw = (values or {}).get(displayed['name'], '')
        # Browsers blank invalid native date/number values, even if the HTML
        # contains the original text. Retain that text during storage errors too.
        if raw and item['kind'] in ('date', 'datetime-local', 'number', 'year'):
            try:
                if item['kind'] == 'date':
                    date.fromisoformat(raw)
                    valid = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw))
                elif item['kind'] == 'datetime-local':
                    datetime.fromisoformat(raw)
                    valid = bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?', raw))
                else:
                    valid = bool(re.fullmatch(r'-?(?:[0-9]+|[0-9]*\.[0-9]+)(?:[eE][+-]?[0-9]+)?', raw))
            except ValueError:
                valid = False
            if not valid:
                displayed['input_kind'] = 'text'
        result.append(displayed)
    return result


def intake_page(get_service, consume, location):
    service = get_service()
    unfinished_service = UnfinishedVisitService(service.repository.path)
    unfinished_id = request.form.get('unfinished_id', '') if request.method == 'POST' else request.args.get('unfinished', '')
    unfinished_revision = int(request.form.get('unfinished_revision', '0')) if request.method == 'POST' else 0
    if request.method == 'POST':
        values, rows, data, issues = read_submission()
    elif unfinished_id:
        saved = unfinished_service.get(unfinished_id)
        unfinished_revision = saved['revision']
        values, rows, data, issues = read_submission(MultiDict(saved['fields']))
    else:
        values = {'mode': 'existing' if request.args.get('patient_id') else 'new',
                  'patient_id': request.args.get('patient_id', ''), 'status': 'DRAFT',
                  'creation_time': datetime.now().isoformat(timespec='minutes')}
        rows = {section: ['0'] for section in SECTIONS}
        data, issues = {}, []
    status, patients = 200, []
    try:
        patients = service.list_patients()
        if request.method == 'POST' and request.form.get('intent') == 'save_later':
            saved = unfinished_service.save(request.form.to_dict(flat=False), unfinished_id, unfinished_revision)
            consume()
            flash('visit.saved_unfinished')
            return redirect(location('queue'), code=303)
        if request.method == 'POST' and request.form.get('intent') != 'language':
            if request.files:
                issues.append(issue('form', None, None, 'error.form'))
            if not issues:
                bundle = IntakeService(service.repository).create(data,
                    (unfinished_id, unfinished_revision) if unfinished_id else None)
                consume()
                flash('status.saved')
                return redirect(location('bundle', bundle_id=bundle.ID), code=303)
            status = 422
        elif request.method == 'POST' and values.get('had_errors') == '1':
            # Do not resurrect errors for a row removed before changing language.
            issues = [error for error in g.previous_errors
                      if error['row_index'] is None
                      or str(error['row_index']) in rows.get(error['section'], [])]
    except IntakeError as error:
        issues, status = error.issues, 422
    except (ValueError, OverflowError):
        issues, status = [issue('form', None, None, 'visit.save_conflict')], 409
    except StorageError as error:
        log_storage_error(current_app.config['DATABASE'], 'intake', error)
        issues, status = [issue('form', None, None, 'error.unavailable')], 503

    patient_fields = display_fields(FORMS['patient'], values=values)
    existing_fields = display_fields([field('patient_id', 'patient', 'select', choices=[
        (patient.ID, patient.name + (f' · {patient.birth_year}' if patient.birth_year else '') + ' · ' + str(index + 1)) for index, patient in enumerate(patients)])])
    referral_fields = display_fields(FORMS['bundle'][1:], values=values)
    groups = []
    all_fields = {item['name']: item for item in patient_fields + existing_fields + referral_fields}
    all_fields['mode'] = dict(control_id='mode', label='intake.patient_mode')
    for section in SECTIONS:
        entries = []
        for key in rows[section] + ['__ROW__']:
            items = section_fields(section)
            if section == 'results':
                items[-1]['choices'] = [(order_key, str(position + 1) + ' · ' + values.get('orders.' + order_key + '.name', ''))
                                        for position, order_key in enumerate(rows['orders'])]
            items = display_fields(items, section + '.' + key + '.', values)
            all_fields.update({item['name']: item for item in items})
            entries.append(dict(key=key, fields=items))
        opened = any(key.startswith(section + '.') and key != section + '.rows' and value.strip()
                     for key, value in values.items())
        groups.append(dict(name=section, entries=entries[:-1], prototype=entries[-1], opened=opened))
    displayed_errors, field_errors = [], []
    for error in issues:
        section, row, name = error['section'], error['row_index'], error['field']
        control_name = (section + '.' + str(row) + '.' if row is not None else '') + (name or '')
        target = all_fields.get(control_name)
        control_id = target['control_id'] if target else 'intake-form' if section == 'form' else 'section-' + section
        row_number = rows.get(section, []).index(str(row)) + 1 if str(row) in rows.get(section, []) else None
        displayed_errors.append(dict(error, control_id=control_id, row_number=row_number,
                                     label=target['label'] if target else None))
        if target:
            field_errors.append(dict(field=control_name, code=error['code']))
    return render_template('intake.html', title='page.bundle_new', fields=[], values=values,
        patient_fields=patient_fields, existing_fields=existing_fields, referral_fields=referral_fields,
        groups=groups, issues=issues, errors=displayed_errors, field_errors=field_errors,
        back=location('queue'), unfinished_id=unfinished_id,
        unfinished_revision=unfinished_revision), status
