"""Correction/recovery HTTP adapters; services own all data mutations."""
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from flask import current_app, g, request, render_template, redirect, flash, abort
from sehatraasta.presentation.catalogs import translate

from sehatraasta.domain import AttachmentCategory, Language, Provenance, ProvenanceType
from sehatraasta.services.correction_service import CorrectionService, RECORDS
from sehatraasta.storage.db import connect_database
from sehatraasta.services.recovery_service import RecoveryService
from sehatraasta.services.attachment_validation import validate_attachment_filename, validate_attachment_size
from sehatraasta.storage.errors import StorageError, log_storage_error
from .forms import FORMS, field, convert_form


def service():
    from .routes import bundles
    return bundles()


def choice_patients():
    return [(patient.ID, patient.name + (f' · {patient.birth_year}' if patient.birth_year else '') + f' · {index+1}')
        for index, patient in enumerate(service().list_patients())]


def choice_visits():
    visits=service().list_bundles()
    labels=[owner.name + (f' · {owner.birth_year}' if owner.birth_year else '') + ' · ' +
        (visit.source_facility or '') + ' · ' + (visit.medical_date_value or translate('date.unknown',g.language)) +
        (' · '+visit.attachments[0].name if visit.attachments else '') for owner,visit in visits]
    return [(visit.ID,label + (' · '+translate('date.saved',g.language)+' '+visit.creation_time.isoformat(timespec='minutes')+f' · {index+1}' if labels.count(label)>1 else ''))
        for index,((owner,visit),label) in enumerate(zip(visits,labels))]


def editor(title, fields, initial, patient, visit, operation, back, kind='correction'):
    from .routes import consume
    values = request.form.to_dict() if request.method == 'POST' else initial
    revision = values.get('revision', patient._storage_revision)
    errors, status = [], 200
    if request.method == 'POST' and request.form.get('intent') != 'language':
        parsed, errors = convert_form(fields, values, request.files)
        if not errors:
            try:
                destination = operation(int(revision), parsed)
                consume()
                flash('status.saved')
                return redirect(destination or back, code=303)
            except (ValueError, KeyError, OverflowError) as error:
                errors = [{'field':None, 'code':'correction.changed' if 'changed' in str(error) else 'correction.invalid'}]
                status = 409 if 'changed' in str(error) or 'duplicate' in str(error) else 422
            except (StorageError, OSError) as error:
                log_storage_error(current_app.config['DATABASE'], 'correction_form', error)
                errors, status = [{'field':None, 'code':'error.unavailable'}], 503
        elif errors:
            status = 422
    return render_template('form.html', title=title, fields=fields, values=values,
        revision=revision, patient=patient, visit=visit, errors=errors, kind=kind,
        back=back, subject=None), status


def visit_editor(visit_id):
    from .routes import location
    patient, visit = service().get_bundle_owner(visit_id)
    fields = [field('patient_id', 'patient', 'select', choices=choice_patients()),
        field('source_facility', 'sending_facility', required=False), field('destination', required=False),
        field('medical_date_kind', 'date_kind', 'select', choices=[(kind, 'date.'+kind) for kind in ('unknown','exact','approximate')]),
        field('medical_date_value', 'medical_date', required=False)]
    fields[-1]['hint'] = 'date.help'
    initial = {'patient_id':patient.ID, 'source_facility':visit.source_facility, 'destination':visit.destination,
        'medical_date_kind':visit.medical_date_kind, 'medical_date_value':visit.medical_date_value or ''}
    def save(revision, data):
        CorrectionService(service().repository.path).visit(visit_id, revision,
            patient_id=data['patient_id'], facility=data['source_facility'], destination=data['destination'],
            date_kind=data['medical_date_kind'], date_value=data['medical_date_value'] or None)
    return editor('correction.visit', fields, initial, patient, visit, save, location('bundle', bundle_id=visit_id))


def remove_page(kind, identifier):
    from .routes import consume, location
    if kind == 'patient':
        patient, visit = service().get_patient(identifier), None
        label = patient.name
    elif kind == 'visit':
        patient, visit = service().get_bundle_owner(identifier)
        label = visit.source_facility or patient.name
    else:
        visit, original = service().get_attachment_owner(identifier)
        patient, _ = service().get_bundle_owner(visit.ID)
        label = original.name
    error, status = None, 200
    if request.method == 'POST':
        try:
            if request.form.get('confirm') != 'yes':
                raise ValueError('confirmation required')
            RecoveryService(service().repository.path).remove(kind, identifier, int(request.form.get('revision','')))
            consume()
            flash('recovery.removed')
            return redirect(location('removed_items'), code=303)
        except (ValueError, OverflowError) as problem:
            error, status = ('error.required',422) if request.form.get('confirm')!='yes' else ('recovery.parent_pending',409) if 'cleanup' in str(problem) else ('correction.changed',409)
        except StorageError as problem:
            log_storage_error(current_app.config['DATABASE'], 'remove_form', problem)
            error, status = 'error.unavailable', 503
    back = location('patient', patient_id=patient.ID) if kind == 'patient' else location('bundle', bundle_id=visit.ID)
    return render_template('recovery_action.html', title='recovery.remove', patient=patient,
        visit=visit, label=label, revision=patient._storage_revision, action='remove',
        error=error, back=back), status


def register(pages):
    @pages.route('/records/<kind>/<identifier>/edit',methods=['GET','POST'])
    def record_edit(kind, identifier):
        from .routes import location
        if kind not in RECORDS:
            abort(404)
        table,key,mapping = RECORDS[kind]
        connection = connect_database(service().repository.path,read_only=True)
        try:
            row = connection.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identifier,)).fetchone()
            if row is None:
                abort(404)
            patient,visit = service().get_bundle_owner(row['bundle_id'])
            initial = {name:row[column] for name,column in mapping.items()}
            if kind=='cost':
                initial['amount'] = str(Decimal(row['amount_paisa'])/100)
            if kind=='result':
                linked = connection.execute('SELECT test_name FROM investigation_orders WHERE order_id=?',(row['investigation_order_id'],)).fetchone()
                initial['order_name'] = linked[0] if linked else ''
        finally:
            connection.close()
        fields = [dict(item) for item in FORMS[kind]]
        if kind in ('result','imaging'):
            link_name = 'order_name' if kind=='result' else 'attachment_id'
            choices = [(order.name,order.name+' · '+str(order.date)) for order in visit.investigation_orders] if kind=='result' else [(paper.ID,paper.name) for paper in visit.attachments]
            next(item for item in fields if item['name']==link_name).update(kind='select',choices=choices)
        fields.extend([field('destination_visit','destination_visit','select',choices=choice_visits()),field('unlink','unlink','checkbox',required=False)])
        fields[-1]['default'] = False
        initial['destination_visit'] = visit.ID
        def save(revision,data):
            destination,unlink = data.pop('destination_visit'),data.pop('unlink')
            CorrectionService(service().repository.path).record(kind,identifier,revision,data,destination,unlink)
            return location('bundle',bundle_id=destination)
        return editor('correction.record',fields,initial,patient,visit,save,location('bundle',bundle_id=visit.ID),kind=kind)

    @pages.route('/records/<kind>/<identifier>/remove',methods=['GET','POST'])
    def record_remove(kind, identifier):
        from .routes import location,consume
        if kind not in RECORDS:
            abort(404)
        table,key,_ = RECORDS[kind]
        connection = connect_database(service().repository.path,read_only=True)
        try:
            row = connection.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identifier,)).fetchone()
            if row is None:
                abort(404)
            patient,visit = service().get_bundle_owner(row['bundle_id'])
        finally:
            connection.close()
        error,status = None,200
        if request.method=='POST':
            try:
                if request.form.get('confirm')!='yes':
                    raise ValueError('confirmation required')
                RecoveryService(service().repository.path).remove_record(kind,identifier,int(request.form.get('revision','')))
                consume(); flash('recovery.removed')
                return redirect(location('removed_items'),code=303)
            except (ValueError,OverflowError):
                error,status = 'correction.changed',409
            except StorageError:
                error,status = 'error.unavailable',503
        label=next((str(row[column])[:120] for column in ('verbatim_name','test_name','verbatim_text','modality','facility','category') if column in row.keys() and row[column]),kind)
        if 'date' in row.keys(): label+=' · '+str(row['date'])
        if kind=='cost': label+=' · PKR '+str(Decimal(row['amount_paisa'])/100)
        return render_template('recovery_action.html',title='recovery.remove',patient=patient,visit=visit,
            label=label,revision=patient._storage_revision,action='remove',error=error,
            back=location('bundle',bundle_id=visit.ID)),status

    @pages.route('/patients/<patient_id>/edit', methods=['GET','POST'])
    def patient_edit(patient_id):
        from .routes import location
        patient = service().get_patient(patient_id)
        fields = [dict(item) for item in FORMS['patient']]
        return editor('correction.patient', fields,
            {'name':patient.name,'birth_year':patient.birth_year or '', 'language':patient.language.name},
            patient, None, lambda revision, data: CorrectionService(service().repository.path).patient(patient_id,
                revision, data['name'], data['birth_year'], data['language'].name), location('patient',patient_id=patient_id))

    @pages.route('/attachments/<attachment_id>/edit', methods=['GET','POST'])
    def document_edit(attachment_id):
        from .routes import location
        visit, original = service().get_attachment_owner(attachment_id)
        patient, _ = service().get_bundle_owner(visit.ID)
        choices = choice_visits()
        fields = [field('name','document_name'), field('category','document_type','select', choices=[(item.value,item.value) for item in AttachmentCategory]),
            field('date',kind='date',required=False,convert=date.fromisoformat),
            field('destination_visit','destination_visit','select',choices=choices),
            field('unlink','unlink','checkbox',required=False)]
        fields[2]['default'] = None
        fields[-1]['default'] = False
        fields.extend(dict(item) for item in FORMS['attachment'] if item['name'] in ('source_type','source','source_identifier'))
        connection = connect_database(service().repository.path,read_only=True)
        try:
            source = dict(connection.execute('SELECT source_type,source_identifier FROM managed_attachments WHERE attachment_id=?',(attachment_id,)).fetchone())
            source['source_type'] = ProvenanceType(source['source_type']).name
            source['source_identifier'] = source['source_identifier'] or ''
        finally:
            connection.close()
        def save(revision, data):
            CorrectionService(service().repository.path).document(attachment_id, revision,
                name=data['name'], category=data['category'], document_date=data['date'],
                destination_visit=data['destination_visit'], unlink=data['unlink'],
                provenance=Provenance(data['source_type'],data['source'] or None,data['source_identifier'] or None))
            return location('bundle',bundle_id=data['destination_visit'])
        return editor('correction.document', fields, {'name':original.name, 'category':original.category,
            'date':original.date.isoformat() if original.date else '', 'destination_visit':visit.ID,
            'source':original.source if original.source!='source not supplied' else '', **source},
            patient, visit, save, location('bundle', bundle_id=visit.ID))

    @pages.route('/attachments/<attachment_id>/replace', methods=['GET','POST'])
    def document_replace(attachment_id):
        from .routes import location
        visit, original = service().get_attachment_owner(attachment_id)
        patient, _ = service().get_bundle_owner(visit.ID)
        def save(revision, data):
            uploaded = data['file']
            extension = validate_attachment_filename(uploaded.filename)
            content = uploaded.stream.read(5242881)
            validate_attachment_size(len(content))
            with TemporaryDirectory(prefix='sr-replacement-') as folder:
                path = Path(folder)/(uuid4().hex + extension)
                path.write_bytes(content)
                CorrectionService(service().repository.path).replace(attachment_id, revision, path, uploaded.filename)
        return editor('correction.replace', [field('file',kind='file')], {}, patient, visit,
            save, location('bundle',bundle_id=visit.ID), kind='replacement')

    @pages.get('/removed')
    def removed_items():
        return render_template('removed_items.html',title='recovery.title',items=RecoveryService(service().repository.path).list())

    @pages.route('/removed/<item_id>/<action>', methods=['GET','POST'])
    def recovery_action(item_id, action):
        from .routes import consume, location
        if action not in ('restore','permanent'):
            abort(404)
        recovery = RecoveryService(service().repository.path)
        item = next((item for item in recovery.list() if item['item_id']==item_id), None)
        if item is None:
            abort(404)
        error, status = None, 200
        if request.method == 'POST':
            try:
                if request.form.get('confirm') != 'yes':
                    raise ValueError('confirmation required')
                if action == 'restore':
                    recovery.restore(item_id)
                    flash('recovery.restored')
                else:
                    pending = recovery.permanent(item_id)
                    flash('recovery.pending' if pending else 'recovery.deleted')
                consume()
                return redirect(location('removed_items'), code=303)
            except (ValueError, OverflowError):
                error, status = 'recovery.conflict', 409
            except StorageError as problem:
                log_storage_error(current_app.config['DATABASE'], 'recovery_form', problem)
                error, status = 'error.unavailable', 503
        return render_template('recovery_action.html',title='recovery.'+action,action=action,
            label=item['label'],context=item['context'],error=error,back=location('removed_items')), status
