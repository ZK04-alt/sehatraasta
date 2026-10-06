from datetime import datetime
from decimal import Decimal
import re
import sqlite3

import pytest

from sehatraasta.domain import Language, ReferralStatus
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.intake_service import IntakeService, IntakeError, SECTIONS
from sehatraasta.services.identifiers import IDAllocator
from sehatraasta.storage import SQLiteRepository, StorageError


def intake_data():
    return dict(mode='new', patient=dict(name='Amina Demo', birth_year='1980', language='URDU'),
        referral=dict(creation_time='2026-09-22T12:00', source_facility='Demo BHU', destination='Demo Hospital', status='DRAFT'),
        medications=[dict(_key=0, name='Demo item', strength='As supplied', dose='As supplied', route='As supplied',
                          frequency='As supplied', duration='As supplied', instructions='Original مثال', source='Demo source')],
        orders=[dict(_key=0, name='Same test name', date='2026-09-21', source='Demo source', workflow_status='ORDERED'),
                dict(_key=3, name='Same test name', date='2026-09-22', source='Other source', workflow_status='ORDERED')],
        results=[dict(_key=0, name='Demo result', date='2026-09-22', source='Demo source', interpretation='Verbatim demo', order_key='3')],
        imaging=[dict(_key=0, modality='X-ray', body_part='Demo part', date='2026-09-22', facility='Demo BHU', report='Demo report')],
        instructions=[dict(_key=0, category='Follow-up', language='URDU', text='Original مثال', source='Demo source', date='2026-09-22')],
        costs=[dict(_key=0, category='TRAVEL', amount='0.10', date='2026-09-22', source='Demo receipt',
                    source_type='receipt', source_identifier='Demo A', note=''),
               dict(_key=1, category='TRAVEL', amount='0.20', date='2026-09-22', source='Demo receipt',
                    source_type='receipt', source_identifier='Demo B', note='')])


def snapshot(path):
    with sqlite3.connect(path) as connection:
        return list(connection.iterdump())


def test_complete_intake_round_trip_and_local_order_mapping(tmp_path):
    path = tmp_path / 'intake.sqlite'
    repository = SQLiteRepository(path)
    bundle = IntakeService(repository).create(intake_data())
    patient = SQLiteRepository(path).list_patients()[0]
    saved = patient.referrals[0]
    assert re.fullmatch(r'PT-[2-9A-HJ-NP-Z]{6}', patient.ID)
    assert re.fullmatch(r'SR-[A-Z]{12}-\d{3}', bundle.ID)
    assert saved.diagnostic_results[0].investigation_order is saved.investigation_orders[1]
    assert saved.total_cost_pkr() == Decimal('0.30')
    assert saved.medication_item[0].instructions == 'Original مثال'
    assert saved.imaging_items[0].Attachment_ID is None
    assert len(saved.instructions) == 1
    assert not hasattr(saved.investigation_orders[0], 'ID')
    assert not hasattr(saved.instructions[0], 'ID')
    for group, prefix in [(saved.medication_item, 'MD'), (saved.diagnostic_results, 'DR'),
                          (saved.imaging_items, 'IM'), (saved.cost_entries, 'CE')]:
        assert all(re.fullmatch(prefix + r'-[2-9A-HJ-NP-Z]{6}', row.ID) for row in group)
        assert len({row.ID for row in group}) == len(group)


@pytest.mark.parametrize('existing', [False, True])
def test_intake_commits_once(tmp_path, monkeypatch, existing):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    data = intake_data()
    if existing:
        BundleService(repository).create_patient('PK-001', 'Original Demo', 1980, Language.ENGLISH)
        data.update(mode='existing', patient_id='PK-001', patient={'name': 'Must not replace'})
    calls = []
    original = repository._save
    def save(patient, adding):
        calls.append(adding)
        assert patient.referrals[-1].diagnostic_results
        assert patient.referrals[-1].cost_entries
        return original(patient, adding)
    monkeypatch.setattr(repository, '_save', save)
    IntakeService(repository).create(data)
    assert calls == [not existing]
    assert len(repository.list_patients()) == 1
    if existing:
        assert repository.get_patient('PK-001').name == 'Original Demo'


@pytest.mark.parametrize('existing', [False, True])
def test_failure_after_real_child_inserts_rolls_back_everything(tmp_path, monkeypatch, existing):
    path = tmp_path / 'data.sqlite'
    repository = SQLiteRepository(path)
    data = intake_data()
    if existing:
        service = BundleService(repository)
        service.create_patient('PK-001', 'Original Demo', 1980, Language.URDU)
        service.create_bundle('PK-001', 'RB-001', datetime(2026, 9, 20), 'Before', 'Unchanged', ReferralStatus.DRAFT)
        data.update(mode='existing', patient_id='PK-001')
    before = snapshot(path)
    original = repository._write_bundle
    written = []
    def fail_after_records(connection, patient_id, bundle):
        original(connection, patient_id, bundle)
        if bundle.diagnostic_results:
            assert connection.execute('SELECT count(*) FROM cost_entries').fetchone()[0] == 2
            written.append(bundle.ID)
            raise sqlite3.OperationalError('PRIVATE medical text must not be logged')
    monkeypatch.setattr(repository, '_write_bundle', fail_after_records)
    with pytest.raises(StorageError):
        IntakeService(repository).create(data)
    assert written
    assert snapshot(path) == before
    assert 'PRIVATE' not in (tmp_path / 'storage-errors.log').read_text()
    patients = repository.list_patients()
    assert len(patients) == int(existing)
    if existing:
        assert patients[0].referrals[0].destination == 'Unchanged'


def test_all_parse_errors_reported_before_any_save(tmp_path, monkeypatch):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    data = intake_data()
    data['medications'].append(dict(data['medications'][0], _key=5, name=''))
    data['costs'][1]['amount'] = 'not a number'
    data['results'][0]['date'] = '2026-99-99'
    def forbidden(*args, **kwargs):
        pytest.fail('Validation must precede persistence')
    monkeypatch.setattr(repository, '_save', forbidden)
    with pytest.raises(IntakeError) as caught:
        IntakeService(repository).create(data)
    fields = {(e['section'], e['row_index'], e['field']) for e in caught.value.issues}
    assert fields == {('medications', 5, 'name'), ('costs', 1, 'amount'), ('results', 0, 'date')}
    assert all(set(e) == {'section', 'row_index', 'field', 'code'} for e in caught.value.issues)
    assert repository.list_patients() == []


@pytest.mark.parametrize('amount', ['-1', 'NaN', 'Infinity', '0.001', '92233720368547758.08'])
def test_invalid_costs_rejected_before_write(tmp_path, amount):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    data = intake_data()
    data['costs'][0]['amount'] = amount
    with pytest.raises(IntakeError) as caught:
        IntakeService(repository).create(data)
    assert any(e['field'] == 'amount' for e in caught.value.issues)
    assert repository.list_patients() == []


def test_blank_rows_ignored_partial_rows_rejected(tmp_path):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    data = intake_data()
    for section in SECTIONS:
        data[section] = [{'_key': 0}]
    IntakeService(repository).create(data)
    assert len(repository.list_patients()) == 1
    data['medications'][0]['name'] = 'Partial demo'
    with pytest.raises(IntakeError):
        IntakeService(repository).create(data)
    assert len(repository.list_patients()) == 1


@pytest.mark.parametrize('order_key,result_date', [('99', '2026-09-22'), ('3', '2026-09-20')])
def test_invalid_order_link_and_result_date(tmp_path, order_key, result_date):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    data = intake_data()
    data['results'][0].update(order_key=order_key, date=result_date)
    with pytest.raises(IntakeError) as caught:
        IntakeService(repository).create(data)
    assert caught.value.issues[0]['field'] in ('order_key', 'date')
    assert repository.list_patients() == []


def test_allocator_reserves_same_submission_ids_and_has_ten_attempt_limit(tmp_path, monkeypatch):
    allocator = IDAllocator(SQLiteRepository(tmp_path / 'data.sqlite'))
    letters = iter('A' * 12 + 'B' * 6)
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: next(letters))
    assert allocator.allocate('medication') == 'MD-AAAAAA'
    assert allocator.allocate('medication') == 'MD-BBBBBB'
    calls = []
    def repeated(_):
        calls.append(1)
        return 'A'
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', repeated)
    with pytest.raises(StorageError):
        allocator.allocate('medication')
    assert len(calls) == 60


def test_allocator_includes_records_in_other_bundles(tmp_path, monkeypatch):
    repository = SQLiteRepository(tmp_path / 'data.sqlite')
    bundle = IntakeService(repository).create(intake_data())
    used = bundle.medication_item[0].ID
    letters = iter(used.split('-')[1] + 'Z' * 6)
    monkeypatch.setattr('sehatraasta.services.identifiers.secrets.choice', lambda _: next(letters))
    assert IDAllocator(repository).allocate('medication') == 'MD-ZZZZZZ'
