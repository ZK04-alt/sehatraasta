"""Thin HTTP adapters over tested services. No SQL and no clinical decisions."""
import base64
import re
from dataclasses import fields as dataclass_fields
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from time import time
from urllib.parse import urlencode

from flask import Blueprint, current_app, g, request, render_template, redirect, url_for, flash, send_file, session, jsonify
from sehatraasta.services.qr_image import render_qr_png

from sehatraasta.domain import Provenance
from sehatraasta.presentation.errors import error_from_exception
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.completeness_service import CompletenessService
from sehatraasta.services.web_transfer_service import WebTransferService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.patient_deletion_service import PatientDeletionService
from sehatraasta.services.visit_deletion_service import VisitDeletionService
from sehatraasta.services.doctor_report_service import DoctorReportService, ReportDocumentError, ReportSelectionError, supplied
from sehatraasta.services.qr_service import QRService, verify_payload
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.services.passport_service import PassportService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.storage.errors import StorageError
from .forms import FORMS, convert_form, display_value
from .intake import intake_page
from .document_capture import capture_page
from sehatraasta.domain.medical_dates import visit_sort_key
from sehatraasta.services.unfinished_visit_service import UnfinishedVisitService


pages = Blueprint('pages', __name__)


def bundles():
    if 'bundles' not in current_app.extensions:
        current_app.extensions['bundles'] = BundleService(SQLiteRepository(current_app.config['DATABASE']))
    return current_app.extensions['bundles']


def location(endpoint, **values):
    return url_for('pages.' + endpoint, lang=g.language, **values)


def consume():
    if g.form_nonce:
        current_app.extensions['used_forms'][g.form_nonce] = time()


def form_page(kind, title, operation, target, initial=None, fields=None, subject=None):
    fields = fields or FORMS[kind]
    values = dict(request.form) if request.method == 'POST' else (initial or {})
    errors, status = [], 200
    if request.method == 'POST' and request.form.get('intent') != 'language':
        parsed, errors = convert_form(fields, values, request.files)
        if not errors:
            try:
                next_page = operation(parsed)
                consume()
                flash('status.deleted' if kind == 'delete' else 'status.saved')
                return redirect(next_page or target, code=303)
            except ValueError as error:
                presented = error_from_exception(error)
                error_field = next((item['name'] for item in fields
                    if re.search(r'\b' + re.escape(item['name'].lower().replace('_', ' ')) + r'\b', str(error).lower())), fields[0]['name'])
                errors = [{'field': error_field, 'code': presented.code}]
                status = 409 if 'duplicate' in str(error) else 422
            except StorageError as error:
                from sehatraasta.storage.errors import log_storage_error
                log_storage_error(current_app.config['DATABASE'], 'web_save', error)
                errors = [{'field': None, 'code': 'error.unavailable'}]
                status = 503
        if errors and status == 200:
            status = 422
    elif request.method == 'POST' and request.form.get('had_errors') == '1':
        # Keep signed display codes, not private values, when changing language.
        errors = g.previous_errors
    return render_template('form.html', title=title, fields=fields, values=values,
                           errors=errors, back=target, kind=kind, subject=subject), status


@pages.get('/')
@pages.get('/bundles')
def queue():
    service = bundles()
    return render_template('queue.html', title='page.bundles', rows=sorted(service.list_bundles(), key=lambda row: visit_sort_key(row[1])),
        unfinished=UnfinishedVisitService(service.repository.path).list())


@pages.post('/visits/unfinished')
def save_unfinished_visit():
    service = UnfinishedVisitService(bundles().repository.path)
    try:
        saved = service.save(request.form.to_dict(flat=False), request.form.get('unfinished_id', ''),
                             int(request.form.get('unfinished_revision', '0')))
        endpoint = 'document_new' if request.form.get('capture') == 'paper' else 'bundle_new'
        return jsonify(dict(saved, resume_url=location(endpoint, unfinished=saved['draft_id'])))
    except (ValueError, OverflowError):
        return jsonify(error='visit.save_conflict'), 409
    except StorageError:
        return jsonify(error='error.unavailable'), 503


@pages.get('/patients')
def patients():
    return render_template('patients.html', title='page.patients', patients=bundles().list_patients())


@pages.route('/patients/new', methods=['GET', 'POST'])
def patient_new():
    def save(data):
        bundles().create_patient(None, data['name'], data['birth_year'], data['language'])
    return form_page('patient', 'page.patient_new', save, location('patients'))


@pages.get('/patients/<patient_id>')
def patient(patient_id):
    return render_template('patient.html', title='page.patient', patient=bundles().get_patient(patient_id))


@pages.route('/patients/<patient_id>/delete', methods=['GET', 'POST'])
def patient_delete(patient_id):
    item = bundles().get_patient(patient_id)
    error, status = None, 200
    if request.method == 'POST':
        if request.form.get('confirm') != 'yes':
            error, status = 'error.required', 422
        else:
            try:
                revision = int(request.form.get('revision', ''))
                pending = PatientDeletionService(bundles().repository.path).delete(patient_id, revision)
            except ValueError:
                error, status = 'patient.delete_changed', 409
            else:
                consume()
                flash('patient.delete_cleanup' if pending else 'status.deleted')
                return redirect(location('patients'), code=303)
    return render_template('patient_delete.html', title='action.patient_delete', patient=item, error=error), status


@pages.route('/bundles/new', methods=['GET', 'POST'])
def bundle_new():
    return intake_page(bundles, consume, location)


@pages.route('/documents/new', methods=['GET', 'POST'])
def document_new():
    return capture_page(bundles, consume, location)


def record_sections(bundle):
    groups = [('page.medication', bundle.medication_item), ('page.order', bundle.investigation_orders),
              ('page.result', bundle.diagnostic_results), ('page.imaging', bundle.imaging_items),
              ('page.instruction', bundle.instructions), ('page.encounters', bundle.encounters)]
    result = []
    labels = {'ID': 'id', 'workflow_status': 'test_status', 'Attachment_ID': 'link',
              'clinician_display_text': 'reviewer', 'source_note': 'source'}
    for title, records in groups:
        rows = []
        for item in records:
            values = []
            for field in dataclass_fields(item):
                value = getattr(item, field.name)
                if field.name in ('ID', 'Attachment_ID'):
                    continue
                if field.name == 'investigation_order':
                    value = value.name if value else None
                if supplied(value):
                    label = labels.get(field.name, field.name)
                    if field.name == 'name':
                        if title == 'page.medication':
                            label = 'medicine_name'
                        elif title in ('page.order', 'page.result'):
                            label = 'test_name'
                    values.append(('field.' + label, display_value(value)))
            rows.append(values)
        result.append((title, rows))
    return result


@pages.get('/bundles/<bundle_id>/costs')
@pages.get('/bundles/<bundle_id>/attachments')
@pages.get('/bundles/<bundle_id>')
def bundle(bundle_id):
    owner, bundle = bundles().get_bundle_owner(bundle_id)
    return render_template('bundle.html', title='page.bundle', patient=owner, bundle=bundle,
        groups=CompletenessService().group_categories(bundle), sections=record_sections(bundle),
        total=bundles().total_cost_pkr(bundle_id), printing=False,
        context=ReferralContextService(bundles().repository.path).get(bundle_id))


@pages.route('/bundles/<bundle_id>/context', methods=['GET', 'POST'])
def referral_context(bundle_id):
    bundles().get_bundle(bundle_id)
    service = ReferralContextService(bundles().repository.path)
    return form_page('context', 'page.context', lambda data: service.save(bundle_id, data),
        location('bundle', bundle_id=bundle_id), service.get(bundle_id))


@pages.post('/bundles/<bundle_id>/passport')
def passport_export(bundle_id):
    if request.form.get('confirm') != 'yes':
        return render_template('error.html', title='error.required', code='error.required', status=422), 422
    data = PassportService(bundles().repository.path).export(bundle_id)
    consume()
    return send_file(BytesIO(data), mimetype='application/zip', as_attachment=True, download_name='sehatraasta-passport.zip')


@pages.route('/passports/import', methods=['GET', 'POST'])
def passport_import():
    summary, error, status = None, None, 200
    if request.method == 'POST':
        uploaded = request.files.get('archive')
        try:
            if uploaded is None or not uploaded.filename:
                raise ValueError('invalid passport file')
            content = uploaded.stream.read(50 * 1024 * 1024 + 1)
            digest = sha256(content).hexdigest()
            service = PassportService(bundles().repository.path)
            summary = service.preview(content)
            if request.form.get('intent') == 'import':
                if session.get('passport_digest') != digest:
                    raise ValueError('check passport first')
                found = service.import_passport(content, confirmed=True)
                consume()
                session.pop('passport_digest', None)
                flash('passport.imported')
                return redirect(location('bundle', bundle_id=found), code=303)
            session['passport_digest'] = digest
        except ValueError as problem:
            code = str(problem)
            error = 'passport.duplicate' if code in ('passport already imported', 'document already stored') else 'passport.check_first' if code == 'check passport first' else 'passport.invalid'
            status = 422
    return render_template('passport_import.html', title='page.passport_import', summary=summary, error=error), status


@pages.route('/bundles/<bundle_id>/edit', methods=['GET', 'POST'])
def bundle_edit(bundle_id):
    item = bundles().get_bundle(bundle_id)
    def save(data):
        bundles().update_bundle(bundle_id, data['source_facility'], data['destination'], item.status)
    return form_page('edit', 'page.bundle_edit', save, location('bundle', bundle_id=bundle_id),
                     {'source_facility': item.source_facility, 'destination': item.destination, 'status': item.status.name})


@pages.route('/bundles/<bundle_id>/<kind>/new', methods=['GET', 'POST'])
def record_new(bundle_id, kind):
    kinds = {'medications': 'medication', 'orders': 'order', 'results': 'result', 'imaging': 'imaging',
             'instructions': 'instruction', 'costs': 'cost'}
    if kind not in kinds:
        from flask import abort
        abort(404)
    item = bundles().get_bundle(bundle_id)
    name = kinds[kind]
    def save(d):
        service = bundles()
        if name == 'medication':
            service.add_medication(bundle_id, None, d['name'], d['strength'], d['dose'], d['route'],
                                   d['frequency'], d['duration'], d['instructions'], d['source'])
        elif name == 'order':
            service.add_order(bundle_id, d['name'], d['date'], d['source'], d['workflow_status'])
        elif name == 'result':
            service.add_result(bundle_id, None, d['name'], d['date'], d['source'], d['interpretation'], d['order_name'])
        elif name == 'imaging':
            service.add_imaging(bundle_id, None, d['modality'], d['body_part'], d['date'], d['facility'], d['report'], d['attachment_id'])
        elif name == 'instruction':
            service.add_instruction(bundle_id, d['category'], d['language'], d['text'], d['source'], d['date'])
        else:
            service.add_cost(bundle_id, None, d['category'], d['amount'], d['date'], d['source'],
                             d['note'], d['source_type'], d['source_identifier'])
    fields = [dict(field) for field in FORMS[name]]
    if name in ('result', 'imaging'):
        link_name = 'order_name' if name == 'result' else 'attachment_id'
        choices = [(order.name, order.name + ' · ' + str(order.date)) for order in item.investigation_orders] if name == 'result' else [(document.ID, document.name + ' · ' + str(document.date)) for document in item.attachments]
        link = next(field for field in fields if field['name'] == link_name)
        link.update(kind='select', choices=choices)
    return form_page(name, 'page.cost_new' if name == 'cost' else 'page.' + name, save, location('bundle', bundle_id=bundle_id), fields=fields)


@pages.route('/bundles/<bundle_id>/reviews', methods=['GET', 'POST'])
def reviews(bundle_id):
    bundles().get_bundle(bundle_id)
    def save(d):
        bundles().set_category_review(bundle_id, d['category'], d['state'], d['text'], d['time'], d['note'])
    return form_page('review', 'page.reviews', save, location('bundle', bundle_id=bundle_id))


@pages.route('/bundles/<bundle_id>/attachments/new', methods=['GET', 'POST'])
def attachment_new(bundle_id):
    item = bundles().get_bundle(bundle_id)
    choices = [('medication_list:1', 'Medication list')]
    for group, records in [('order_id', item.investigation_orders), ('instruction_id', item.instructions),
                           ('result_id', item.diagnostic_results), ('imaging_id', item.imaging_items)]:
        for record in records:
            identifier = record._storage_id if group in ('order_id', 'instruction_id') else record.ID
            label = (getattr(record, 'name', None) or getattr(record, 'modality', None) or getattr(record, 'category', ''))
            choices.append((group + ':' + str(identifier), str(label) + ' — ' + str(record.date)))
    fields = [dict(field) for field in FORMS['attachment']]
    next(field for field in fields if field['name'] == 'link')['choices'] = choices
    def save(d):
        links = {}
        if d['link']:
            if d['link'] not in dict(choices):
                raise ValueError('invalid attachment link')
            key, value = d['link'].split(':', 1)
            links[key] = True if key == 'medication_list' else int(value) if key in ('order_id', 'instruction_id') else value
        provenance = Provenance(d['source_type'], d['source'] or None, d['source_identifier'])
        WebTransferService(bundles()).upload(d['file'], bundle_id, None, d['category'], d['date'],
                                            provenance, **links)
    return form_page('attachment', 'page.attachment_new', save, location('bundle', bundle_id=bundle_id), fields=fields)


@pages.get('/attachments/<attachment_id>/download')
def download(attachment_id):
    content, mime = FileService(bundles().repository.path).retrieve(attachment_id)
    owner, document = bundles().get_attachment_owner(attachment_id)
    from sehatraasta.services.attachment_validation import validate_attachment_filename
    validate_attachment_filename(document.name)
    return send_file(BytesIO(content), mimetype=mime, as_attachment=True, download_name=document.name)


@pages.get('/attachments/<attachment_id>/content')
def attachment_content(attachment_id):
    content, mime = FileService(bundles().repository.path).retrieve(attachment_id)
    return send_file(BytesIO(content), mimetype=mime, as_attachment=False)


@pages.get('/attachments/<attachment_id>/print-pages')
def attachment_print_pages(attachment_id):
    renderer = current_app.config.get('RENDER_REPORT_PDF')
    if renderer is None:
        from flask import abort
        abort(404)
    content, mime = FileService(bundles().repository.path).retrieve(attachment_id)
    if mime != 'application/pdf':
        return jsonify(error='report.failed'), 422
    try:
        return jsonify(pages=renderer(content))
    except Exception:
        return jsonify(error='report.failed'), 422


@pages.route('/attachments/<attachment_id>/delete', methods=['GET', 'POST'])
def delete(attachment_id):
    owner, attachment = bundles().get_attachment_owner(attachment_id)
    def save(d):
        FileService(bundles().repository.path).delete(attachment_id)
    return form_page('delete', 'page.delete', save, location('bundle', bundle_id=owner.ID), subject=attachment.name)


@pages.get('/bundles/<bundle_id>/audit')
def audit(bundle_id):
    item = bundles().get_bundle(bundle_id)
    events = FileService(bundles().repository.path).audit.list_events(bundle_id)
    names = {document.ID: document.name for document in item.attachments}
    from sehatraasta.presentation.catalogs import translate
    for event in events:
        event['attachment_id'] = names.get(event['attachment_id'], translate('page.attachments', g.language))
    return render_template('audit.html', title='page.audit', events=events, bundle_id=bundle_id)


@pages.get('/bundles/<bundle_id>/print')
def print_bundle(bundle_id):
    owner, item = bundles().get_bundle_owner(bundle_id)
    return report_response(owner, [item.ID], True, False)


def doctor_report(patient_id, identifiers, include_documents, include_costs, document_ids=None):
    patient, visits = DoctorReportService(bundles()).collect(patient_id, identifiers, include_documents, document_ids)
    for visit in visits:
        item = visit['bundle']
        payload = QRService(bundles().repository.path).for_bundle(item.ID)
        visit['qr'] = base64.b64encode(render_qr_png(payload)).decode('ascii')
        visit['sections'] = [(title, rows) for title, rows in record_sections(item) if rows]
    choices = [('lang', g.language), ('selection', 'individual')]
    choices.extend(('visit', identifier) for identifier in identifiers)
    choices.extend(('document', document.ID) for visit in visits for document in visit['documents'])
    if include_costs:
        choices.append(('costs', 'yes'))
    selection_url = url_for('pages.patient_print', patient_id=patient_id) + '?' + urlencode(choices)
    return render_template('doctor_report.html', title='report.title', patient=patient, visits=visits, selection_url=selection_url,
        include_costs=include_costs, printing=True, prepared_at=datetime.now().strftime('%Y-%m-%d %H:%M'))


@pages.get('/patients/<patient_id>/print')
def patient_print(patient_id):
    item = bundles().get_patient(patient_id)
    chosen = request.args.getlist('visit')
    documents = request.args.getlist('document')
    costs = request.args.get('costs') == 'yes'
    if request.args.get('preview') == 'yes':
        return report_response(item, chosen, request.args.get('documents') == 'yes', costs,
                               documents if request.args.get('selection') == 'individual' else None)
    values = dict(title='report.choose', patient=item, chosen=chosen,
                  documents=documents, include_costs=costs, document_error=None, error=None)
    return render_template('report_selection.html', **values)


def report_response(patient, chosen, include_documents, costs, documents=None):
    # Normalize legacy all-original links to explicit choices for the recovery form.
    effective = documents if documents is not None else [document.ID
        for visit in patient.referrals if include_documents and visit.ID in chosen
        for document in visit.attachments]
    values = dict(title='report.choose', patient=patient, chosen=chosen,
                  documents=effective, include_costs=costs, document_error=None, error=None)
    try:
        return doctor_report(patient.ID, chosen, include_documents, costs, documents)
    except ReportSelectionError as error:
        return render_template('report_selection.html', **{**values,
            'error':'report.document_visit_error', 'document_error':error.document_name}), 422
    except ReportDocumentError as error:
        return render_template('report_selection.html', **{**values,
            'error':'report.selection_error', 'document_error':error.document_name}), 422
    except ValueError:
        code = 'report.no_visit' if not chosen else 'report.selection_error'
        return render_template('report_selection.html', **{**values, 'error':code}), 422
    except StorageError:
        return render_template('report_selection.html', **{**values, 'error':'report.selection_error'}), 503


@pages.route('/bundles/<bundle_id>/delete', methods=['GET', 'POST'])
def visit_delete(bundle_id):
    owner, item = bundles().get_bundle_owner(bundle_id)
    error, status = None, 200
    if request.method == 'POST':
        if request.form.get('confirm') != 'yes':
            error, status = 'error.required', 422
        else:
            try:
                pending = VisitDeletionService(bundles().repository.path).delete(bundle_id, int(request.form.get('revision', '')))
            except ValueError:
                error, status = 'patient.delete_changed', 409
            else:
                consume()
                flash('patient.delete_cleanup' if pending else 'status.deleted')
                return redirect(location('patient', patient_id=owner.ID), code=303)
    return render_template('visit_delete.html', title='visit.remove', patient=owner, bundle=item, error=error), status


@pages.get('/sharing')
def sharing_help():
    return render_template('sharing.html', title='sharing.title')


@pages.post('/bundles/<bundle_id>/export')
def export(bundle_id):
    data = WebTransferService(bundles()).export(bundle_id)
    consume()
    return send_file(BytesIO(data), mimetype='application/json', as_attachment=True, download_name='sehatraasta-bundle.json')


@pages.route('/lookup', methods=['GET', 'POST'])
def lookup():
    if request.method == 'POST' and request.form.get('intent') != 'language':
        payload = request.form.get('payload', '')
        try:
            service = QRService(bundles().repository.path)
            found = service.lookup(payload) if payload.startswith('{') else service.lookup_short(payload)
            consume()
            return redirect(location('bundle', bundle_id=found), code=303)
        except ValueError:
            return render_template('form.html', title='page.lookup', fields=FORMS['lookup'], values=dict(request.form),
                errors=[{'field': 'payload', 'code': 'error.not_found'}], back=location('queue'), kind='lookup'), 422
    return form_page('lookup', 'page.lookup', lambda data: None, location('queue'))


@pages.route('/backups', methods=['GET', 'POST'])
def backup():
    if request.method == 'POST' and request.form.get('intent') != 'language' and request.form.get('confirm') == 'yes':
        data = WebTransferService(bundles()).backup()
        consume()
        return send_file(BytesIO(data), mimetype='application/zip', as_attachment=True, download_name='sehatraasta-backup.zip')
    return form_page('backup', 'page.backup', lambda data: None, location('queue'))


@pages.route('/restore', methods=['GET', 'POST'])
def restore():
    errors, summary, restored = [], None, None
    if request.method == 'POST' and request.form.get('intent') != 'language':
        uploaded = request.files.get('archive')
        if not uploaded or not uploaded.filename:
            errors = [{'field': 'archive', 'code': 'error.required'}]
        else:
            data = uploaded.stream.read()
            uploaded.stream.seek(0)
            digest = sha256(data).hexdigest()
            confirmed = request.form.get('intent') == 'restore'
            if confirmed and session.get('restore_digest') != digest:
                errors = [{'field': 'archive', 'code': 'error.check_first'}]
            else:
                try:
                    summary, restored = WebTransferService(bundles()).restore(uploaded, confirm=confirmed)
                    session['restore_digest'] = digest
                    if confirmed:
                        activate = current_app.config.get('ACTIVATE_RESTORE')
                        if activate:
                            activate(restored)
                        consume()
                        session.pop('restore_digest', None)
                except ValueError:
                    errors = [{'field': 'archive', 'code': 'error.backup'}]
    return render_template('restore.html', title='page.restore', fields=FORMS['restore'], values={}, errors=errors,
                           summary=summary, restored=restored, back=location('queue'), kind='restore'), 422 if errors else 200


@pages.get('/privacy')
@pages.get('/terms')
def policy():
    kind = request.path.strip('/')
    return render_template('policy.html', title='page.' + kind, policy=kind)


@pages.get('/favicon.ico')
def favicon():
    return current_app.send_static_file('favicon.svg')
