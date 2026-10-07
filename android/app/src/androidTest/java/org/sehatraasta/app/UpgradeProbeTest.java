package org.sehatraasta.app;

import androidx.test.rule.ActivityTestRule;
import com.chaquo.python.Python;
import org.json.JSONObject;
import org.junit.Rule;
import org.junit.Test;

/** Run seed on the immutable baseline, then verify after signature-compatible upgrade. */
public class UpgradeProbeTest {
    @Rule public ActivityTestRule<MainActivity> activity=new ActivityTestRule<>(MainActivity.class);
    private void execute(String code) throws Exception {
        long deadline=System.currentTimeMillis()+90000;
        while(!Python.isStarted() && System.currentTimeMillis()<deadline) Thread.sleep(250);
        if(!Python.isStarted()) throw new AssertionError("Packaged Python did not start");
        Python python=Python.getInstance();
        boolean ready=false;
        while(System.currentTimeMillis()<deadline) {
            ready="True".equals(python.getModule("builtins").callAttr("eval",
                "getattr(__import__('sehatraasta.android_runtime',fromlist=['_server']),'_server',None) is not None",
                python.getModule("builtins").callAttr("dict")).toString());
            if(ready) break;
            Thread.sleep(250);
        }
        if(!ready) throw new AssertionError("Packaged local server did not become ready");
        python.getModule("builtins").callAttr("exec",code,python.getModule("builtins").callAttr("dict"));
    }
    @Test public void rejectCurrentArchives() throws Exception {
        android.os.Bundle args=androidx.test.platform.app.InstrumentationRegistry.getArguments();
        String backup=JSONObject.quote(args.getString("backupBase64")).replace("\\/","/");
        String passport=JSONObject.quote(args.getString("passportBase64")).replace("\\/","/");
        execute("from pathlib import Path\nimport base64\nimport sehatraasta.android_runtime as runtime\n"
            +"from sehatraasta.services.bundle_service import BundleService\nfrom sehatraasta.storage import SQLiteRepository\n"
            +"from sehatraasta.services.dataset_backup import DatasetBackupService\nfrom sehatraasta.services.passport_service import PassportService\n"
            +"app=runtime._server.app.app\ndb=Path(app.config['DATABASE'])\nbefore=db.read_bytes()\n"
            +"archive=db.parent/'fictional-current-backup.zip'\narchive.write_bytes(base64.b64decode("+backup+"))\n"
            +"for kind,operation in [('backup',lambda:DatasetBackupService(db).restore(archive,db.parent/'future-rejected-restore',confirmed=True)),('passport',lambda:PassportService(db).import_passport(base64.b64decode("+passport+"),confirmed=True))]:\n"
            +" try: operation()\n except ValueError: pass\n else: raise AssertionError(kind+' accepted by immutable baseline')\n assert db.read_bytes()==before\n"
            +"assert not (db.parent/'future-rejected-restore').exists()\nassert BundleService(SQLiteRepository(db)).get_patient('PK-901').name=='Fictional immutable APK upgrade'\narchive.unlink()\n");
    }
    @Test public void seedBaseline() throws Exception {
        execute("from pathlib import Path\nfrom datetime import datetime,date\nfrom decimal import Decimal\n"
            +"from sehatraasta.storage import SQLiteRepository\nfrom sehatraasta.domain import Language,ReferralStatus,AttachmentCategory,Provenance,ProvenanceType,CostCategory\n"
            +"from sehatraasta.services.bundle_service import BundleService\nfrom sehatraasta.services.file_service import FileService\nfrom sehatraasta.services.qr_service import QRService\n"
            +"import sehatraasta.android_runtime as runtime\napp=runtime._server.app.app\ndb=Path(app.config['DATABASE'])\ns=BundleService(SQLiteRepository(db))\n"
            +"s.create_patient('PK-901','Fictional immutable APK upgrade',1980,Language.ENGLISH)\n"
            +"s.create_bundle('PK-901','RB-901',datetime(2020,1,2),'Fictional legacy clinic','',ReferralStatus.DRAFT)\n"
            +"s.add_cost('RB-901','CO-901',CostCategory.TRAVEL,Decimal('25.10'),date(2020,1,2),'Fictional paper')\n"
            +"paper=db.parent/'fictional-upgrade.pdf'\npaper.write_bytes(b'%PDF-1.4\\nFictional immutable APK original')\n"
            +"FileService(db).import_file('RB-901','AT-901',paper,AttachmentCategory.OTHER,date(2020,1,2),Provenance(ProvenanceType.NOT_SUPPLIED))\n"
            +"token=QRService(db).for_bundle('RB-901')\n(db.parent/'fictional-upgrade-token').write_text(token)\n");
    }
    @Test public void verifyUpgrade() throws Exception {
        execute("from pathlib import Path\nfrom decimal import Decimal\n"
            +"from sehatraasta.storage import SQLiteRepository\nfrom sehatraasta.services.bundle_service import BundleService\n"
            +"from sehatraasta.services.file_service import FileService\nfrom sehatraasta.services.qr_service import QRService\n"
            +"import sehatraasta.android_runtime as runtime\napp=runtime._server.app.app\ndb=Path(app.config['DATABASE'])\ns=BundleService(SQLiteRepository(db))\n"
            +"assert s.get_patient('PK-901').name=='Fictional immutable APK upgrade'\n"
            +"assert s.get_patient('PK-901').birth_year==1980\n"
            +"v=s.get_bundle('RB-901')\nassert v.creation_time.isoformat()=='2020-01-02T00:00:00'\n"
            +"assert v.medical_date_kind=='unknown' and v.medical_date_value is None\n"
            +"assert v.total_cost_pkr()==Decimal('25.10')\n"
            +"assert FileService(db).retrieve('AT-901')[0]==b'%PDF-1.4\\nFictional immutable APK original'\n"
            +"assert QRService(db).for_bundle('RB-901')==(db.parent/'fictional-upgrade-token').read_text()\n"
            +"from sehatraasta.services.web_transfer_service import WebTransferService\nfrom sehatraasta.services.dataset_backup import DatasetBackupService\n"
            +"backup=WebTransferService(s).backup()\nassert backup[:2]==b'PK'\n"
            +"archive=db.parent/'fictional-after-upgrade.zip'\narchive.write_bytes(backup)\n"
            +"restored=db.parent/'fictional-after-upgrade-restored'\nDatasetBackupService(db).restore(archive,restored,confirmed=True)\n"
            +"assert FileService(restored/'sehatraasta.sqlite').retrieve('AT-901')[0]==FileService(db).retrieve('AT-901')[0]\n"
            +"response=app.test_client().get('/patients/PK-901/print?preview=yes&selection=individual&visit=RB-901&lang=en')\n"
            +"assert response.status_code==200 and b'Fictional immutable APK upgrade' in response.data\n"
            +"assert b'Find this saved visit' in response.data\n");
    }
}
