package org.sehatraasta.app;

import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebView;
import androidx.test.rule.ActivityTestRule;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Rule;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.json.JSONObject;
import org.json.JSONTokener;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.os.SystemClock;
import android.graphics.Rect;
import android.os.Bundle;
import android.content.ContentValues;
import android.provider.MediaStore;
import android.net.Uri;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/** End-to-end test runs under the separate org.sehatraasta.app.test app ID. */
@org.junit.FixMethodOrder(org.junit.runners.MethodSorters.NAME_ASCENDING)
public class OfflineFlowTest {
    @Test public void a0CameraDeniedReturnsToLookup() throws Exception {
        enableNativeInspection();
        waitFor("document.querySelector('main')");
        assertEquals(android.content.pm.PackageManager.PERMISSION_DENIED,
            activity.getActivity().checkSelfPermission(android.Manifest.permission.CAMERA));
        open("/lookup?lang=en", "typeof window.srQRResult==='function'");
        js("document.querySelector('[data-scan-camera]').click()");
        waitNative("com.android.permissioncontroller:id/permission_deny_button");
        // Permission-dialog animation can invalidate the first accessibility
        // node/bounds; inject a real touch using the settled current window.
        Thread.sleep(700);
        AccessibilityNodeInfo deny=waitNative("com.android.permissioncontroller:id/permission_deny_button");
        Rect bounds=new Rect();deny.getBoundsInScreen(bounds);
        long time=android.os.SystemClock.uptimeMillis();
        android.view.MotionEvent down=android.view.MotionEvent.obtain(time,time,android.view.MotionEvent.ACTION_DOWN,bounds.centerX(),bounds.centerY(),0);
        android.view.MotionEvent up=android.view.MotionEvent.obtain(time,time+50,android.view.MotionEvent.ACTION_UP,bounds.centerX(),bounds.centerY(),0);
        down.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);up.setSource(android.view.InputDevice.SOURCE_TOUCHSCREEN);
        try {
            assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().injectInputEvent(down,true));
            assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().injectInputEvent(up,true));
        } finally {down.recycle();up.recycle();}
        waitNative("android.webkit.WebView");
        waitFor("document.querySelector('[data-scan-status]').innerText.includes('unavailable')");
        assertTrue(js("document.querySelector('[data-scan-status]').innerText").contains("printed code"));
    }
    @Test public void zCorrectionRecoveryAndArchiveBoundsOffline() throws Exception {
        waitFor("document.querySelector('main')");
        // This runs in the packaged Python runtime, using only a separate fictional DB.
        String root = activity.getActivity().getCacheDir().getAbsolutePath();
        String code = "from pathlib import Path\nfrom tempfile import TemporaryDirectory\n"
            + "from datetime import datetime\nfrom io import BytesIO\nimport zipfile\n"
            + "from sehatraasta.storage import SQLiteRepository\nfrom sehatraasta.domain import Language, ReferralStatus\n"
            + "from sehatraasta.services.bundle_service import BundleService\n"
            + "from sehatraasta.services.correction_service import CorrectionService\n"
            + "from sehatraasta.services.recovery_service import RecoveryService\n"
            + "from sehatraasta.services.archive_reader import read_checked_members\n"
            + "with TemporaryDirectory(dir=" + JSONObject.quote(root).replace("\\/", "/") + ") as folder:\n"
            + " db=Path(folder)/'fictional.sqlite'\n s=BundleService(SQLiteRepository(db))\n"
            + " s.create_patient('PK-900','Fictional packaged recovery',None,Language.ENGLISH)\n"
            + " s.create_bundle('PK-900','RB-900',datetime(2026,10,7),'','',ReferralStatus.DRAFT)\n"
            + " CorrectionService(db).visit('RB-900',s.get_patient('PK-900')._storage_revision,patient_id='PK-900',facility='Fictional',destination='',date_kind='approximate',date_value='2008')\n"
            + " r=RecoveryService(db)\n item=r.remove('visit','RB-900',s.get_patient('PK-900')._storage_revision)\n r.restore(item)\n"
            + " assert s.get_bundle('RB-900').medical_date_value=='2008'\n"
            + "for method in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED,zipfile.ZIP_BZIP2,zipfile.ZIP_LZMA):\n"
            + " out=BytesIO()\n content=b'Fictional'*32768\n"
            + " with zipfile.ZipFile(out,'w',method) as a: a.writestr('sample',content)\n"
            + " with zipfile.ZipFile(BytesIO(out.getvalue())) as a: assert read_checked_members(a,a.infolist(),len(content))=={'sample':content}\n";
        com.chaquo.python.Python python=com.chaquo.python.Python.getInstance();
        python.getModule("builtins").callAttr("exec", code,python.getModule("builtins").callAttr("dict"));
        js("location.href='/documents/new?lang=en'");
        waitFor("document.querySelector('#file') && document.querySelector('#name')");
        assertEquals("false", js("document.querySelector('#birth_year').required"));
    }
    @Rule public ActivityTestRule<MainActivity> activity = new ActivityTestRule<>(MainActivity.class);

    @org.junit.After public void closeOwnedNativeOverlays() throws Exception {
        // The isolated emulator's test provider must not poison later cases.
        android.os.ParcelFileDescriptor command=InstrumentationRegistry.getInstrumentation().getUiAutomation()
            .executeShellCommand("am force-stop com.android.documentsui");
        try(java.io.InputStream stream=new android.os.ParcelFileDescriptor.AutoCloseInputStream(command)) {
            while(stream.read()!=-1) { }
        }
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> activity.getActivity().startActivity(
            new android.content.Intent(activity.getActivity(),MainActivity.class)
                .addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP|android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP)));
    }

    private WebView findWeb(View view) {
        if (view instanceof WebView) return (WebView) view;
        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            for (int i = 0; i < group.getChildCount(); i++) {
                WebView result = findWeb(group.getChildAt(i));
                if (result != null) return result;
            }
        }
        return null;
    }

    private void revealRecordDetails() throws Exception {
        js("document.querySelectorAll('details:not(.help-disclosure)').forEach(d=>{if(!d.open)d.querySelector('summary').click()})");
    }

    private String js(String code) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>();
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            WebView web = findWeb(activity.getActivity().getWindow().getDecorView());
            web.evaluateJavascript(code, value -> { result.set(value); done.countDown(); });
        });
        assertTrue("WebView callback timed out", done.await(15, TimeUnit.SECONDS));
        return result.get();
    }

    private void assertReportSurfaceWhite() {
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            WebView web = findWeb(activity.getActivity().getWindow().getDecorView());
            View root = (View) web.getParent();
            assertEquals(android.graphics.Color.WHITE,
                    ((android.graphics.drawable.ColorDrawable) root.getBackground()).getColor());
        });
    }

    private void waitFor(String predicate) throws Exception {
        long deadline = System.currentTimeMillis() + 90000;
        while (System.currentTimeMillis() < deadline) {
            if ("true".equals(js("Boolean(document.readyState==='complete' && (" + predicate + "))"))) return;
            Thread.sleep(250);
        }
        fail("Page did not become ready: " + js("document.body ? document.body.innerText : location.href"));
    }

    private String stringValue(String expression) throws Exception {
        return (String) new JSONTokener(js(expression)).nextValue();
    }

    private void tap(String selector) throws Exception {
        js("document.querySelector(" + JSONObject.quote(selector) + ").scrollIntoView({block:'center'})");
        Thread.sleep(250);
        JSONObject point = new JSONObject(js("(()=>{const r=document.querySelector("
                + JSONObject.quote(selector) + ").getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,w:innerWidth}})()"));
        float[] screen = new float[2];
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() -> {
            WebView web = findWeb(activity.getActivity().getWindow().getDecorView());
            int[] location = new int[2]; web.getLocationOnScreen(location);
            float scale = web.getWidth() / (float) point.optDouble("w");
            screen[0] = location[0] + (float) point.optDouble("x") * scale;
            screen[1] = location[1] + (float) point.optDouble("y") * scale;
        });
        long now = SystemClock.uptimeMillis();
        InstrumentationRegistry.getInstrumentation().sendPointerSync(MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, screen[0], screen[1], 0));
        InstrumentationRegistry.getInstrumentation().sendPointerSync(MotionEvent.obtain(now, now + 100, MotionEvent.ACTION_UP, screen[0], screen[1], 0));
        Thread.sleep(700); // Let the provider window and accessibility tree settle.
    }

    private void open(String path, String ready) throws Exception {
        js("location.href=" + JSONObject.quote(path));
        String pathname = path.split("\\?")[0];
        waitFor("location.pathname===" + JSONObject.quote(pathname) + " && (" + ready + ")");
    }

    private void fill(String... pairs) throws Exception {
        for (int i = 0; i < pairs.length; i += 2) {
            String selector = "[name=\"" + pairs[i] + "\"]";
            String result = js("(()=>{const e=document.querySelector(" + JSONObject.quote(selector)
                    + ");if(!e)return false;e.value=" + JSONObject.quote(pairs[i + 1])
                    + ";e.dispatchEvent(new Event('input',{bubbles:true}));"
                    + "e.dispatchEvent(new Event('change',{bubbles:true}));return true})()");
            assertEquals("Missing field: " + pairs[i], "true", result);
        }
    }

    private void addRecord(String bundle, String kind, String... pairs) throws Exception {
        open(bundle + "/" + kind + "/new", "document.querySelector('form.entry-form')");
        fill(pairs);
        js("document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname===" + JSONObject.quote(bundle));
    }

    private AccessibilityNodeInfo nativeNode(AccessibilityNodeInfo node, String value) {
        if (node == null) return null;
        if (value.equals(String.valueOf(node.getText()))
                || value.equals(String.valueOf(node.getContentDescription()))
                || String.valueOf(node.getContentDescription()).startsWith(value + ", ")
                || value.equals(node.getViewIdResourceName())
                || value.equals(String.valueOf(node.getClassName()))) return node;
        for (int i = 0; i < node.getChildCount(); i++) {
            AccessibilityNodeInfo found = nativeNode(node.getChild(i), value);
            if (found != null) return found;
        }
        return null;
    }

    private AccessibilityNodeInfo waitNative(String value) throws Exception {
        long deadline = System.currentTimeMillis() + 15000;
        do {
            android.app.UiAutomation automation = InstrumentationRegistry.getInstrumentation().getUiAutomation();
            for (android.view.accessibility.AccessibilityWindowInfo window : automation.getWindows()) {
                if (!window.isFocused()) continue;
                AccessibilityNodeInfo root = window.getRoot();
                if (root != null) root.refresh();
                AccessibilityNodeInfo found = nativeNode(root, value);
                if (found != null && found.refresh() && nativeNode(found, value) != null) return found;
            }
            Thread.sleep(200);
        } while (System.currentTimeMillis() < deadline);
        for (android.view.accessibility.AccessibilityWindowInfo window :
                InstrumentationRegistry.getInstrumentation().getUiAutomation().getWindows()) {
            if (window.isFocused()) logNative(window.getRoot());
        }
        throw new AssertionError("Native control did not appear: " + value);
    }

    private void logNative(AccessibilityNodeInfo node) {
        if (node == null) return;
        android.util.Log.i("SRNativeTest", "control " + node.getViewIdResourceName()
                + " text=" + node.getText() + " description=" + node.getContentDescription());
        for (int i = 0; i < node.getChildCount(); i++) logNative(node.getChild(i));
    }

    private void enableNativeInspection() {
        android.app.UiAutomation automation = InstrumentationRegistry.getInstrumentation().getUiAutomation();
        android.accessibilityservice.AccessibilityServiceInfo info = automation.getServiceInfo();
        info.flags |= android.accessibilityservice.AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                | android.accessibilityservice.AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS;
        automation.setServiceInfo(info);
    }

    private void clickNative(String value) throws Exception {
        AccessibilityNodeInfo node = waitNative(value);
        Rect bounds = new Rect();
        node.getBoundsInScreen(bounds);
        android.util.Log.i("SRNativeTest", value + " " + bounds + " actions=" + node.getActionList());
        assertTrue("Disabled native control: " + value, node.isEnabled());
        assertFalse("Native control has no screen bounds", bounds.isEmpty());
        // System file providers can acknowledge accessibility actions without
        // activating their row. Tap the bounds discovered in the current tree.
        android.os.ParcelFileDescriptor command = InstrumentationRegistry.getInstrumentation().getUiAutomation()
                .executeShellCommand("input tap " + bounds.centerX() + " " + bounds.centerY());
        try (java.io.InputStream output = new android.os.ParcelFileDescriptor.AutoCloseInputStream(command)) {
            while (output.read() != -1) { }
        }
        Thread.sleep(250);
    }

    private void saveNative(String name) throws Exception {
        AccessibilityNodeInfo input = waitNative("android.widget.EditText");
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, name);
        assertTrue(input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args));
        clickNative("SAVE");
        // Wait for the provider to return before requesting the next download.
        waitNative("android.webkit.WebView");
        Thread.sleep(500);
    }

    private void pickNative(String name) throws Exception {
        // Android remembers the previous directory. Select a visible file directly.
        Thread.sleep(700);
        boolean visible = false;
        for (android.view.accessibility.AccessibilityWindowInfo window :
                InstrumentationRegistry.getInstrumentation().getUiAutomation().getWindows()) {
            if (window.isFocused() && nativeNode(window.getRoot(), name) != null) visible = true;
        }
        if (!visible) {
            clickNative("Show roots");
            Thread.sleep(700);
            clickNative(name.endsWith(".png") ? "Recent" : "Downloads");
        }
        Thread.sleep(700);
        // Image providers may initially use tiles instead of named file rows.
        for (android.view.accessibility.AccessibilityWindowInfo window :
                InstrumentationRegistry.getInstrumentation().getUiAutomation().getWindows()) {
            if (window.isFocused() && nativeNode(window.getRoot(), "List view") != null) {
                clickNative("List view");
                Thread.sleep(500);
                break;
            }
        }
        AccessibilityNodeInfo node = waitNative(name);
        while (node != null && !node.isFocusable()) node = node.getParent();
        assertNotNull("Document row must support focus", node);
        assertTrue(node.performAction(AccessibilityNodeInfo.ACTION_FOCUS));
        long now = SystemClock.uptimeMillis();
        KeyEvent down = new KeyEvent(now, now, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_ENTER, 0);
        KeyEvent up = new KeyEvent(now, now, KeyEvent.ACTION_UP, KeyEvent.KEYCODE_ENTER, 0);
        down.setSource(android.view.InputDevice.SOURCE_KEYBOARD);
        up.setSource(android.view.InputDevice.SOURCE_KEYBOARD);
        assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().injectInputEvent(down, true));
        assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().injectInputEvent(up, true));
        waitNative("android.webkit.WebView");
    }

    private void verifyNativeFiles(String bundle) throws Exception {
        String suffix = Long.toString(System.currentTimeMillis());
        String document = "sr-verification-" + suffix + ".pdf";
        ContentValues values = new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME, document);
        values.put(MediaStore.Downloads.MIME_TYPE, "application/pdf");
        Uri fixture = activity.getActivity().getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        assertNotNull(fixture);
        try (OutputStream out = activity.getActivity().getContentResolver().openOutputStream(fixture)) {
            out.write(validReport(suffix));
        }
        try {
            open(bundle + "/attachments/new", "document.querySelector('[name=file]')");
            fill("category", "OTHER", "date", "2026-09-27", "source_type", "NOT_SUPPLIED");
            tap("[name=file]");
            pickNative(document);
            waitFor("document.querySelector('[name=file]').files.length===1");
            js("document.querySelector('form.entry-form').submit()");
            waitFor("location.pathname===" + JSONObject.quote(bundle));
            assertTrue(js("document.body.innerText").contains(document));
            js("document.querySelector('a[href*=\"/download\"]').click()");
            saveNative("sr-downloaded-" + suffix + ".pdf");
            js("document.querySelector('form[data-download] button').click()");
            saveNative("sr-export-" + suffix + ".json");
            open(bundle, "document.querySelector('#passport-confirm')");
            js("document.querySelector('#passport-confirm').checked=true;document.querySelector('form[action*=passport] button').click()");
            saveNative("sr-passport-" + suffix + ".zip");
            open("/backups", "document.querySelector('[name=confirm]')");
            js("document.querySelector('[name=confirm]').checked=true;document.querySelector('button[value=save]').click()");
            saveNative("sr-backup-" + suffix + ".zip");
            open(bundle + "/print", "document.documentElement.dataset.reportReady==='yes'");
            assertEquals("1", js("document.querySelectorAll('.document-page img').length"));
            assertReportSurfaceWhite();
            js("document.querySelector('#report-print').click()");
            waitNative("com.android.printspooler:id/destination_spinner");
            clickNative("com.android.printspooler:id/destination_spinner");
            clickNative("Save as PDF");
            waitNative("com.android.printspooler:id/preview_page");
            Thread.sleep(700);
            clickNative("com.android.printspooler:id/print_button");
            saveNative("sr-print-" + suffix + ".pdf");
            open("/restore", "document.querySelector('[name=archive]')");
            tap("[name=archive]");
            pickNative("sr-backup-" + suffix + ".zip");
            waitFor("document.querySelector('[name=archive]').files.length===1");
            js("document.querySelector('button[value=check]').click()");
            waitFor("document.querySelector('button[value=restore]')");
            tap("[name=archive]");
            pickNative("sr-backup-" + suffix + ".zip");
            waitFor("document.querySelector('[name=archive]').files.length===1");
            js("document.querySelector('button[value=restore]').click()");
            waitFor("document.body.innerText.includes('Backup restored and opened.')");
            open(bundle, "document.querySelector('#attachments')");
            revealRecordDetails();
            assertTrue(js("document.body.innerText").contains(document));
            assertTrue(js("document.body.innerText").contains("2,500.10"));
            verifySelectedVisits(bundle);
            assertTrue(activity.getActivity().getSharedPreferences("verification", 0).edit()
                    .putString("document", document).putString("suffix", suffix).commit());
        } finally {
            activity.getActivity().getContentResolver().delete(fixture, null, null);
        }
    }

    private byte[] validReport(String suffix) throws Exception {
        java.io.ByteArrayOutputStream pdf = new java.io.ByteArrayOutputStream();
        String text = "BT /F1 18 Tf 40 720 Td (Fictional test report " + suffix + ") Tj ET\n";
        String[] objects = {
            "<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            "<< /Length " + text.length() + " >>\nstream\n" + text + "endstream"
        };
        pdf.write("%PDF-1.4\n".getBytes(StandardCharsets.US_ASCII));
        int[] offsets = new int[6];
        for (int i=0; i<objects.length; i++) {
            offsets[i+1] = pdf.size();
            pdf.write(((i+1)+" 0 obj\n"+objects[i]+"\nendobj\n").getBytes(StandardCharsets.US_ASCII));
        }
        int xref = pdf.size();
        pdf.write("xref\n0 6\n0000000000 65535 f \n".getBytes(StandardCharsets.US_ASCII));
        for (int i=1; i<6; i++) pdf.write(String.format(java.util.Locale.US,"%010d 00000 n \n",offsets[i]).getBytes(StandardCharsets.US_ASCII));
        pdf.write(("trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"+xref+"\n%%EOF\n").getBytes(StandardCharsets.US_ASCII));
        return pdf.toByteArray();
    }

    private void verifySelectedVisits(String first) throws Exception {
        open(first, "document.querySelector('.record-actions')");
        String patientPath = stringValue("document.querySelector('.bundle-heading a').pathname");
        String patientId = patientPath.substring(patientPath.lastIndexOf('/')+1);
        open("/bundles/new?patient_id="+patientId, "document.querySelector('#intake-form')");
        fill("mode", "existing", "patient_id", patientId, "source_facility", "Second verification clinic", "creation_time", "2026-09-28T10:00");
        js("document.querySelector('#intake-form').submit()");
        waitFor("/^\\/bundles\\/[^/]+$/.test(location.pathname) && location.pathname!='/bundles/new'");
        String second = stringValue("location.pathname");
        open(patientPath+"/print", "document.querySelector('[name=visit]')");
        js("document.querySelectorAll('[name=visit]').forEach(input=>input.checked=true);document.querySelector('form.entry-form').submit()");
        waitFor("document.documentElement.dataset.reportReady==='yes'");
        assertEquals("2", js("document.querySelectorAll('.report-visit').length"));
        assertEquals("0", js("document.querySelectorAll('.document-page img').length"));
        // Individual originals are opt-in, and revising preserves visit choices.
        js("Array.from(document.querySelectorAll('a')).find(a=>a.href.includes('/print?') && a.href.includes('selection=individual')).click()");
        waitFor("document.querySelector('[name=document]')");
        assertEquals("2", js("document.querySelectorAll('[name=visit]:checked').length"));
        assertEquals("0", js("document.querySelectorAll('[name=document]:checked').length"));
        tap("[name=document]");
        js("document.querySelector('form.entry-form').submit()");
        waitFor("document.documentElement.dataset.reportReady==='yes'");
        assertEquals("1", js("document.querySelectorAll('.document-page img').length"));
        assertTrue(stringValue("document.body.innerText").contains("Second verification clinic"));
        assertEquals("\"rgb(255, 255, 255)\"", js("getComputedStyle(document.body).backgroundColor"));
        assertReportSurfaceWhite();
        saveScreen("selected-visit-report.png");
        open(second+"/delete", "document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed' && document.body.innerText.includes('Second verification clinic')");
        // Ordinary removal now keeps recoverable records; exercise real UI undo.
        js("Array.from(document.querySelectorAll('article')).find(a=>a.innerText.includes('Second verification clinic')).querySelector('a[href*=restore]').click()");
        waitFor("document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed' && !Array.from(document.querySelectorAll('article')).some(a=>a.innerText.includes('Second verification clinic'))");
        open(second,"document.body.innerText.includes('Second verification clinic')");
        open(second+"/delete", "document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed'");
        open(patientPath,"document.querySelector('main')");
        assertFalse(stringValue("document.body.innerText").contains("Second verification clinic"));
        open(first, "document.querySelector('#attachments')");
    }

    private void verifyOfflineQR(String bundle) throws Exception {
        open(bundle + "/print", "document.querySelector('img.qr').complete && document.querySelector('img.qr').naturalWidth>0");
        String data = stringValue("document.querySelector('img.qr').src.split(',')[1]");
        byte[] png = android.util.Base64.decode(data, android.util.Base64.DEFAULT);
        String payload = QRImageDecoder.decode(new java.io.ByteArrayInputStream(png));
        assertFalse(payload.contains("Verification medicine"));
        activity.getActivity().getSharedPreferences("verification", 0).edit().putString("qr", payload).commit();
        String name = "sr-qr-" + System.currentTimeMillis() + ".png";
        ContentValues values = new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME, name);
        values.put(MediaStore.Downloads.MIME_TYPE, "image/png");
        values.put(MediaStore.Images.Media.RELATIVE_PATH, android.os.Environment.DIRECTORY_PICTURES);
        values.put(MediaStore.Images.Media.IS_PENDING, 1);
        Uri image = activity.getActivity().getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        try {
            try (OutputStream out = activity.getActivity().getContentResolver().openOutputStream(image)) { out.write(png); }
            ContentValues ready = new ContentValues();
            ready.put(MediaStore.Images.Media.IS_PENDING, 0);
            activity.getActivity().getContentResolver().update(image, ready, null, null);
            open("/lookup", "document.querySelector('[data-scan-image]') && typeof window.srQRResult==='function'");
            if ("true".equals(InstrumentationRegistry.getArguments().getString("qrImageResultOnly"))) {
                // Explicit diagnostic mode tests the result-handler boundary,
                // not selection inside Android's separate document provider.
                InstrumentationRegistry.getInstrumentation().runOnMainSync(() ->
                    activity.getActivity().onActivityResult(12, android.app.Activity.RESULT_OK,
                        new android.content.Intent().setData(image)));
            } else {
                js("document.querySelector('[data-scan-image]').click()");
                pickNative(name);
            }
            waitFor("document.querySelector('[name=payload]').value.startsWith('{')");
            assertEquals(payload, stringValue("document.querySelector('[name=payload]').value"));
            js("document.querySelector('form.entry-form').submit()");
            waitFor("location.pathname===" + JSONObject.quote(bundle));
            open("/lookup", "document.querySelector('[data-scan-camera]')");
            // Granted-camera cancellation is distinct from the denial case.
            InstrumentationRegistry.getInstrumentation().getUiAutomation().grantRuntimePermission(
                activity.getActivity().getPackageName(),android.Manifest.permission.CAMERA);
            js("document.querySelector('[data-scan-camera]').click()");
            waitNative("org.sehatraasta.app.test:id/zxing_status_view");
            assertTrue(InstrumentationRegistry.getInstrumentation().getUiAutomation().performGlobalAction(
                    android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK));
            waitNative("android.webkit.WebView");
            waitFor("(()=>{const s=document.querySelector('[data-qr-scanner]');return Boolean(s.dataset.cancelled)&&s.querySelector('[data-scan-status]').textContent===s.dataset.cancelled})()");
        } finally { activity.getActivity().getContentResolver().delete(image, null, null); }
    }

    @Test public void dSaveUnfinishedOffline() throws Exception {
        waitFor("document.querySelector('a[href*=patients]')");
        open("/bundles/new?lang=en", "document.querySelector('[name=name]')");
        assertEquals("null", js("document.querySelector('[name=status]')"));
        fill("name", "Unfinished Native Demo", "source_facility", "Native Demo Hospital", "destination", "");
        js("document.querySelector('[name=name]').dispatchEvent(new Event('input',{bubbles:true}))");
        waitFor("document.querySelector('[data-autosave-status]').innerText.includes('Saved on this device')");
        String draft = stringValue("document.querySelector('[name=unfinished_id]').value");
        assertTrue(draft.startsWith("UV-"));
        activity.getActivity().getSharedPreferences("verification", 0).edit().putString("unfinished", draft).commit();
        js("Array.from(document.querySelectorAll('a')).find(a=>a.pathname==='/bundles').click()");
        waitFor("location.pathname==='/bundles' && document.body.innerText.includes('Unfinished Native Demo')");
        assertTrue(stringValue("document.body.innerText").contains("Unfinished"));
    }

    @Test public void eResumeUnfinishedOffline() throws Exception {
        waitFor("document.querySelector('a[href*=patients]')");
        String draft = activity.getActivity().getSharedPreferences("verification", 0).getString("unfinished", null);
        assertNotNull("Run save-unfinished first", draft);
        open("/bundles/new?lang=en&unfinished=" + draft, "document.querySelector('[name=name]')");
        assertEquals("Unfinished Native Demo", stringValue("document.querySelector('[name=name]').value"));
        assertEquals("", stringValue("document.querySelector('[name=destination]').value"));
        fill("birth_year", "1980", "language", "URDU");
        js("document.querySelector('button[value=save]').click()");
        waitFor("document.querySelector('.record-actions')");
        assertTrue(stringValue("document.body.innerText").contains("Native Demo Hospital"));
        assertFalse(stringValue("document.body.innerText").contains("Draft"));
        open("/bundles", "document.querySelector('.referral-card')");
        assertEquals("0", js("document.querySelectorAll('a[href*=\"unfinished=" + draft + "\"]').length"));
    }

    @Test public void cMobilePresentationAndTouchFeedback() throws Exception {
        enableNativeInspection();
        waitFor("document.querySelector('.android-app') && document.querySelector('.brand img').complete");
        open("/bundles?lang=en", "document.querySelector('.toolbar .button')");
        assertEquals("\"rgb(242, 238, 229)\"", js("getComputedStyle(document.body).backgroundColor"));
        assertTrue(js("document.querySelector('.brand img').src").contains("wordmark.svg"));
        assertEquals("3", js("document.querySelectorAll('.sidebar a').length"));
        assertEquals("\"rgba(0, 0, 0, 0)\"", js("getComputedStyle(document.querySelector('.toolbar .button')).webkitTapHighlightColor"));
        assertEquals("true", js("document.documentElement.scrollWidth <= innerWidth"));
        saveScreen("referrals-en.png");
        tap(".app-menu > summary");
        assertEquals("true", js("document.querySelector('.app-menu').open"));
        tap(".app-menu a[href*='/backups']");
        waitFor("location.pathname==='/backups'");
        open("/bundles/new", "document.querySelector('#intake-form')");
        assertEquals("0", js("document.querySelectorAll('[data-record-section][open]').length"));
        assertEquals("true", js("getComputedStyle(document.querySelector('[name=name]')).minHeight==='52px'"));
        assertEquals("true", js("document.documentElement.scrollWidth <= innerWidth"));
        saveScreen("new-referral-en.png");
        tap("[name=name]");
        waitFor("document.body.classList.contains('keyboard-open')");
        assertEquals("true", js("getComputedStyle(document.querySelector('.sidebar')).display==='none'"));
        InstrumentationRegistry.getInstrumentation().sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
        waitFor("!document.body.classList.contains('keyboard-open')");
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() ->
            findWeb(activity.getActivity().getWindow().getDecorView()).getSettings().setTextZoom(200));
        Thread.sleep(700);
        assertEquals("true", js("document.documentElement.scrollWidth <= innerWidth"));
        saveScreen("new-visit-large-text.png");
        InstrumentationRegistry.getInstrumentation().runOnMainSync(() ->
            findWeb(activity.getActivity().getWindow().getDecorView()).getSettings().setTextZoom(100));
        for (String language : new String[]{"ur", "ps"}) {
            open("/bundles?lang=" + language, "document.documentElement.lang==='" + language + "'");
            assertEquals("\"rtl\"", js("document.documentElement.dir"));
            assertEquals("true", js("document.documentElement.scrollWidth <= innerWidth"));
            saveScreen("referrals-" + language + ".png");
        }
        open("/bundles?lang=en", "document.documentElement.lang==='en'");
    }

    private void saveScreen(String name) throws Exception {
        android.graphics.Bitmap image = InstrumentationRegistry.getInstrumentation().getUiAutomation().takeScreenshot();
        assertNotNull(image);
        ContentValues values = new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME, "sr-visual-" + name);
        values.put(MediaStore.Downloads.MIME_TYPE, "image/png");
        values.put(MediaStore.Downloads.RELATIVE_PATH, "Download/sr-visual-review");
        Uri destination = activity.getActivity().getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        assertNotNull(destination);
        try (OutputStream out = activity.getActivity().getContentResolver().openOutputStream(destination)) {
            assertTrue(image.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out));
        } finally { image.recycle(); }
    }

    @Test public void aCreateSaveAndRestoreOffline() throws Exception {
        enableNativeInspection();
        String patientName = "Android verification " + System.currentTimeMillis();
        waitFor("document.querySelector('a[href*=patients]')");
        assertTrue(js("location.origin").contains("127.0.0.1"));
        js("location.href='/patients/new'");
        waitFor("document.querySelector('[name=birth_year]')");
        assertFalse(js("document.body.innerText").contains("made-up name"));
        js("document.querySelector('[name=name]').value=" + JSONObject.quote(patientName) + ";"
                + "document.querySelector('[name=birth_year]').value='1990';"
                + "document.querySelector('[name=language]').value='ENGLISH';"
                + "document.querySelector('form.entry-form').submit();");
        waitFor("location.pathname==='/patients' && document.body.innerText.includes(" + JSONObject.quote(patientName) + ")");
        js("Array.from(document.querySelectorAll('tbody tr')).find(r=>r.innerText.includes(" + JSONObject.quote(patientName) + ")).querySelector('a').click()");
        waitFor("/^\\/patients\\/[^/]+$/.test(location.pathname) && location.pathname!='/patients/new' && document.querySelector('a[href*=\"/delete\"]')");
        String patientPath = stringValue("location.pathname");
        String patientId = patientPath.substring(patientPath.lastIndexOf('/') + 1);
        open("/bundles/new?patient_id=" + patientId, "document.querySelector('#intake-form')");
        fill("mode", "existing", "patient_id", patientId,
                "source_facility", "Verification clinic", "destination", "Verification hospital",
                "creation_time", "2026-09-27T10:00");
        js("document.querySelector('#intake-form').submit()");
        waitFor("/^\\/bundles\\/[^/]+$/.test(location.pathname) && location.pathname!='/bundles/new'");
        String bundle = stringValue("location.pathname");
        assertTrue(js("document.body.innerText").contains("Verification hospital"));
        addRecord(bundle, "medications", "name", "Verification medicine", "strength", "10 mg",
                "dose", "1 tablet", "frequency", "Once a day", "duration", "5 days");
        addRecord(bundle, "orders", "name", "Verification test", "date", "2026-09-27",
                "workflow_status", "ORDERED");
        addRecord(bundle, "results", "name", "Verification result", "date", "2026-09-27");
        addRecord(bundle, "imaging", "modality", "X-ray", "body_part", "Verification part",
                "date", "2026-09-27", "facility", "Verification centre");
        addRecord(bundle, "instructions", "category", "Follow-up", "language", "ENGLISH",
                "date", "2026-09-27", "text", "Verification instruction");
        addRecord(bundle, "costs", "category", "TRAVEL", "amount", "2500.10", "date", "2026-09-27");
        revealRecordDetails();
        assertTrue(js("document.body.innerText").contains("2,500.10"));
        // The mobile record groups are collapsed until opened by the reader.
        js("document.querySelectorAll('details.record-section').forEach(d=>d.open=true)");
        assertTrue(js("document.body.innerText").contains("Verification medicine"));
        open(bundle + "/context", "document.querySelector('[name=medical_history]')");
        fill("medical_history", "Verification history", "allergies", "Verification allergy",
                "department", "Orthopaedics", "referral_reason", "Verification reason", "follow_up_date", "2026-10-09");
        js("document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname===" + JSONObject.quote(bundle));
        revealRecordDetails();
        assertTrue(js("document.body.innerText").contains("Verification history"));
        open(bundle + "/reviews", "document.querySelector('[name=state]')");
        fill("category", "IMAGING_REPORTS", "state", "PENDING", "text", "Verification reviewer",
                "time", "2026-09-27T10:00", "note", "Awaiting verification report");
        js("document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname===" + JSONObject.quote(bundle));
        revealRecordDetails();
        assertTrue(js("document.body.innerText").contains("Pending"));
        open(bundle + "?lang=ur", "document.documentElement.lang==='ur'");
        assertEquals("\"rtl\"", js("document.documentElement.dir"));
        open(bundle + "?lang=ps", "document.documentElement.lang==='ps'");
        open(bundle + "?lang=en", "document.documentElement.lang==='en'");
        revealRecordDetails();
        assertTrue(js("document.body.innerText").contains("2,500.10"));
        open(bundle + "/print", "document.documentElement.dataset.reportReady==='yes'");
        assertEquals("true", js("Boolean(document.querySelector('img.qr'))"));
        verifyOfflineQR(bundle);
        verifyNativeFiles(bundle);
        assertTrue(activity.getActivity().getSharedPreferences("verification", 0).edit()
                .putString("patientPath", patientPath).putString("patientName", patientName)
                .putString("bundle", bundle).commit());
        js("location.href='https://example.com/'");
        Thread.sleep(500);
        assertTrue(js("location.origin").contains("127.0.0.1"));
    }

    @Test public void bReopenAndRemoveSavedPatient() throws Exception {
        enableNativeInspection();
        waitFor("document.querySelector('a[href*=patients]')");
        android.content.SharedPreferences saved = activity.getActivity().getSharedPreferences("verification", 0);
        String bundle = saved.getString("bundle", null);
        String patientPath = saved.getString("patientPath", null);
        String patientName = saved.getString("patientName", null);
        assertNotNull("Run the create/restore test first", bundle);
        open(bundle, "document.querySelector('#attachments')");
        revealRecordDetails();
        js("document.querySelectorAll('details.record-section').forEach(d=>d.open=true)");
        String page = stringValue("document.body.innerText");
        for (String value : new String[]{"Verification medicine", "Verification test", "Verification result",
                "Verification centre", "Verification instruction", "Verification history", "Verification allergy",
                "Orthopaedics", "2026-10-09", "2,500.10", saved.getString("document", "")}) {
            assertTrue("Saved record missing after restart: " + value, page.contains(value));
        }
        open(patientPath, "document.querySelector('a[href*=\"/delete\"]')");
        js("document.querySelector('a[href^=\"/patients/\"][href*=\"/delete\"]').click()");
        waitFor("document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed' && document.body.innerText.includes(" + JSONObject.quote(patientName) + ")");
        js("location.href='/patients'");
        waitFor("!document.body.innerText.includes(" + JSONObject.quote(patientName) + ")");
        // Retained originals reserve duplicate bytes and tokens. Confirm an
        // intentional permanent removal of this isolated fixture before import.
        open("/removed?lang=en", "document.querySelector('article')");
        js("Array.from(document.querySelectorAll('article')).find(a=>a.innerText.includes(" + JSONObject.quote(patientName) + ")).querySelector('a[href*=permanent]').click()");
        waitFor("document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed' && !Array.from(document.querySelectorAll('article')).some(a=>a.innerText.includes(" + JSONObject.quote(patientName) + "))");
        // Receive the separately saved referral without replacing any other record.
        open("/passports/import", "document.querySelector('[name=archive]')");
        tap("[name=archive]");
        pickNative("sr-passport-" + saved.getString("suffix", "") + ".zip");
        waitFor("document.querySelector('[name=archive]').files.length===1");
        js("document.querySelector('button[value=check]').click()");
        waitFor("document.querySelector('button[value=import]')");
        assertTrue(stringValue("document.body.innerText").contains(patientName));
        tap("[name=archive]");
        pickNative("sr-passport-" + saved.getString("suffix", "") + ".zip");
        waitFor("document.querySelector('[name=archive]').files.length===1");
        js("document.querySelector('button[value=import]').click()");
        waitFor("/^\\/bundles\\/[^/]+$/.test(location.pathname)");
        String importedBundle = stringValue("location.pathname");
        assertNotEquals(bundle, importedBundle);
        revealRecordDetails();
        js("document.querySelectorAll('details.record-section').forEach(d=>d.open=true)");
        for (String value : new String[]{"Verification history", "Verification medicine", "2,500.10", saved.getString("document", "")}) {
            assertTrue(stringValue("document.body.innerText").contains(value));
        }
        open("/lookup", "document.querySelector('[name=payload]')");
        fill("payload", saved.getString("qr", ""));
        js("document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname===" + JSONObject.quote(importedBundle));
        open("/patients", "document.querySelector('tbody')");
        js("Array.from(document.querySelectorAll('tbody tr')).find(r=>r.innerText.includes(" + JSONObject.quote(patientName) + ")).querySelector('a').click()");
        waitFor("/^\\/patients\\/[^/]+$/.test(location.pathname) && location.pathname!='/patients/new' && document.querySelector('a[href*=\"/delete\"]')");
        js("document.querySelector('a[href^=\"/patients/\"][href*=\"/delete\"]').click()");
        waitFor("document.querySelector('[name=confirm]')");
        js("document.querySelector('[name=confirm]').checked=true;document.querySelector('form.entry-form').submit()");
        waitFor("location.pathname==='/removed' && document.body.innerText.includes(" + JSONObject.quote(patientName) + ")");
        open("/patients", "!document.body.innerText.includes(" + JSONObject.quote(patientName) + ")");
        // The WebView must not navigate the native bridge to an external origin.
        js("location.href='https://example.com/'");
        Thread.sleep(500);
        assertTrue(js("location.origin").contains("127.0.0.1"));
    }
}
