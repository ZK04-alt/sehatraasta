"""Thin multipart adapter for atomic, document-first saving."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from flask import current_app, g, request, render_template, redirect, flash

from sehatraasta.domain import Language
from sehatraasta.domain.medical_dates import validate_medical_date
from sehatraasta.services.attachment_validation import (validate_attachment_filename,
    validate_attachment_size, validate_attachment_signature)
from sehatraasta.services.document_capture_service import DocumentCaptureService
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService
from sehatraasta.storage.errors import StorageError, log_storage_error
from .forms import field


def capture_page(get_service, consume, location):
    service = get_service()
    drafts = UnfinishedVisitService(service.repository.path)
    patients = service.list_patients()
    draft_id = request.form.get('unfinished_id', '') if request.method == 'POST' else request.args.get('unfinished', '')
    revision, errors, status = 0, [], 200
    reopen_details = False
    if request.method == 'POST':
        values = request.form.to_dict()
    elif draft_id:
        saved = drafts.get(draft_id)
        if saved['fields'].get('capture') != ['paper']:
            raise ValueError('wrong unfinished form')
        values = {key: entries[0] for key, entries in saved['fields'].items()}
        revision = saved['revision']
    else:
        values = {'mode': 'existing' if patients else 'new',
            'patient_id': request.args.get('patient_id', ''), 'medical_date_kind': 'unknown'}
    if request.method == 'POST' and request.form.get('intent') == 'language':
        errors = g.previous_errors if request.form.get('had_errors') == '1' else []
    elif request.method == 'POST':
        error_field = 'capture-form'
        try:
            revision = int(values.get('unfinished_revision', '0'))
            if request.form.get('intent') == 'save_later':
                typed = request.form.to_dict(flat=False)
                typed['capture'] = ['paper']
                drafts.save(typed, draft_id, revision)
                consume()
                flash('capture.saved_details')
                return redirect(location('queue'), code=303)
            error_field = 'mode'
            mode = values.get('mode')
            if mode not in ('new', 'existing'):
                raise ValueError('invalid patient mode')
            error_field = 'patient_id' if mode == 'existing' else 'name'
            patient_id = values.get('patient_id', '') if mode == 'existing' else ''
            name = values.get('name', '') if mode == 'new' else ''
            if not (patient_id if mode == 'existing' else name.strip()):
                raise ValueError('required patient')
            if patient_id:
                service.get_patient(patient_id)
            error_field = 'birth_year'
            birth = values.get('birth_year', '') if mode == 'new' else ''
            birth = int(birth) if birth.strip() else None
            error_field = 'medical_date_value'
            kind, value = validate_medical_date(values.get('medical_date_kind', 'unknown'),
                values.get('medical_date_value', '') or None)
            error_field = 'file'
            uploaded = request.files.get('file')
            if uploaded is None or not uploaded.filename:
                raise ValueError('required file')
            extension = validate_attachment_filename(uploaded.filename)
            content = uploaded.stream.read(5242881)
            validate_attachment_size(len(content))
            validate_attachment_signature(extension, content[:8])
            with TemporaryDirectory(prefix='sr-capture-') as folder:
                path = Path(folder) / (uuid4().hex + extension)
                path.write_bytes(content)
                identifier = DocumentCaptureService(service).save(path, patient_id=patient_id,
                    name=name, birth_year=birth, language={'en': Language.ENGLISH, 'ur': Language.URDU, 'ps': Language.PASHTO}[g.language],
                    medical_date_kind=kind, medical_date_value=value,
                    facility=values.get('source_facility', ''), original_name=uploaded.filename,
                    unfinished=(draft_id, revision) if draft_id else None)
            consume()
            flash('status.saved')
            return redirect(location('bundle', bundle_id=identifier), code=303)
        except (ValueError, OverflowError) as error:
            problem=str(error)
            reopen_details = problem == 'unfinished visit changed; reopen before saving'
            code = ('capture.details_changed' if reopen_details else
                    'capture.removed_duplicate' if 'duplicate' in problem and 'Removed items' in problem else
                    'capture.duplicate' if 'duplicate' in problem else
                    'capture.file_large' if problem=='file too large' else
                    'capture.file_type' if error_field=='file' and ('extension' in problem or 'filename' in problem or 'file header' in problem) else
                    'error.date' if error_field == 'medical_date_value' else
                    'error.required' if str(error).startswith('required') else 'error.invalid')
            errors, status = [{'field': error_field, 'code': code}], 409 if reopen_details or 'duplicate' in problem else 422
        except (StorageError, OSError) as error:
            log_storage_error(current_app.config['DATABASE'], 'capture', error)
            errors, status = [{'field': 'capture-form', 'code': 'error.unavailable'}], 503
    # Patient choices preserve distinct identity without displaying an absent birth year.
    choices = [(patient.ID, patient.name + (f' · {patient.birth_year}' if patient.birth_year else '') + f' · {index + 1}')
               for index, patient in enumerate(patients)]
    existing_fields = [field('patient_id', 'patient', 'select', choices=choices)]
    name_fields = [field('name', 'patient_name')]
    optional_fields = [field('birth_year', kind='year', required=False, convert=int),
                       field('source_facility', 'sending_facility', required=False)]
    optional_fields[0]['hint'] = 'help.year'
    if request.method == 'POST':
        try:
            revision = int(values.get('unfinished_revision', '0'))
        except ValueError:
            revision = 0
    return render_template('document_capture.html', title='capture.title', fields=[],
        values=values, errors=errors, existing_fields=existing_fields, name_fields=name_fields,
        optional_fields=optional_fields, unfinished_id=draft_id, unfinished_revision=revision,
        reopen_details=reopen_details), status
