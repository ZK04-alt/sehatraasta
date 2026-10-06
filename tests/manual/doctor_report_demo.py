"""Generate isolated fictional report cases; never write the normal instance."""
from datetime import datetime, date
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageDraw
from sehatraasta.domain import Language, ReferralStatus, Provenance, ProvenanceType, AttachmentCategory
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.services.file_service import FileService
from sehatraasta.services.referral_context import ReferralContextService
from sehatraasta.storage import SQLiteRepository


def fixture_pdf():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for index in (1, 2):
        stream = f'BT /F1 20 Tf 50 760 Td (Fictional laboratory report - page {index}) Tj 0 -40 Td /F1 12 Tf (Not a real patient result. Demonstration only.) Tj ET'.encode()
        objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
        if index == 1:
            objects.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 7 0 R >>')
    data = b'%PDF-1.4\n'
    offsets = [0]
    for number, content in enumerate(objects, 1):
        offsets.append(len(data)); data += f'{number} 0 obj\n'.encode()+content+b'\nendobj\n'
    start = len(data)
    data += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    for offset in offsets[1:]: data += f'{offset:010d} 00000 n \n'.encode()
    data += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()
    return data


def create():
    root = Path('tmp/doctor-report-20261005')/uuid4().hex
    root.mkdir(parents=True)
    service = BundleService(SQLiteRepository(root/'instance/data.sqlite'))
    service.create_patient('PK-001', 'Amina Demo', 1980, Language.URDU)
    for identifier, day, facility in [('RB-001',1,'Lahore clinic A'),('RB-002',2,'Lahore clinic B'),('RB-003',3,'Karachi specialist')]:
        service.create_bundle('PK-001',identifier,datetime(2026,10,day,10),facility,'',ReferralStatus.DRAFT)
    service.add_medication('RB-001','MD-001','Fictional medicine','Example strength','Example dose','','Example frequency','Example duration','','source not supplied')
    ReferralContextService(service.repository.path).save('RB-001',{'medical_history':'Fictional history: first consultation for a demonstration case.'})
    ReferralContextService(service.repository.path).save('RB-002',{'referral_notes':'Fictional note: second consultation and report received.'})
    ReferralContextService(service.repository.path).save('RB-003',{'referral_reason':'Fictional specialist consultation after two earlier visits.','department':'Orthopaedics'})
    pdf = root/'demo-report.pdf'; pdf.write_bytes(fixture_pdf())
    image = Image.new('RGB',(700,850),'white'); draw=ImageDraw.Draw(image)
    draw.text((40,40),'FICTIONAL IMAGE ATTACHMENT',fill='black'); draw.rectangle((150,200,550,700),outline='black',width=4)
    image.save(root/'demo-image.png')
    provenance=Provenance(ProvenanceType.NOT_SUPPLIED,None,None)
    FileService(service.repository.path).import_file('RB-002','AT-001',pdf,AttachmentCategory.OTHER,date(2026,10,2),provenance)
    FileService(service.repository.path).import_file('RB-003','AT-002',root/'demo-image.png',AttachmentCategory.OTHER,date(2026,10,3),provenance)
    print(service.repository.path)


if __name__ == '__main__': create()
