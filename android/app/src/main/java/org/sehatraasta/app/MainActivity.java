package org.sehatraasta.app;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.print.PrintManager;
import android.print.PrintAttributes;
import android.view.View;
import android.webkit.*;
import android.widget.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;
import com.google.zxing.client.android.Intents;

/** Native shell around the same offline referral application used on desktop. */
public class MainActivity extends Activity {
    private static final int PICK_FILE = 10, SAVE_FILE = 11, PICK_QR = 12;
    // Whole-dataset backups support 100 MiB expanded data plus ZIP overhead.
    private static final long MAX_DOWNLOAD = 102L * 1024 * 1024;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private WebView web;
    private LinearLayout root;
    private String origin;
    private ValueCallback<Uri[]> upload;
    private File pendingDownload;
    private boolean downloading;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xfff2eee5);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        TextView loading = new TextView(this);
        loading.setText(R.string.opening);
        loading.setTextColor(0xff303a2b);
        loading.setPadding(32, 48, 32, 48);
        root.addView(loading);
        web = new WebView(this);
        web.setBackgroundColor(0xfff2eee5);
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::handleBack);
        }
        WebSettings settings = web.getSettings();
        settings.setTextZoom(Math.round(getResources().getConfiguration().fontScale * 100));
        settings.setJavaScriptEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setSaveFormData(false);
        settings.setSupportMultipleWindows(false);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);
        web.addJavascriptInterface(new DeviceBridge(), "SRAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return !isLocal(request.getUrl().toString());
            }
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                if (isLocal(request.getUrl().toString())) return null;
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", null,
                        new ByteArrayInputStream(new byte[0]));
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                setPageBackground(url);
            }
            @Override public void onPageFinished(WebView view, String url) {
                setPageBackground(url);
                loading.setVisibility(View.GONE);
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (upload != null) upload.onReceiveValue(null);
                upload = callback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                String[] types = params.getAcceptTypes();
                if (types.length > 0 && !types[0].isEmpty()) intent.putExtra(Intent.EXTRA_MIME_TYPES, types);
                try { startActivityForResult(intent, PICK_FILE); }
                catch (Exception error) { upload.onReceiveValue(null); upload = null; message("No file picker is available."); }
                return true;
            }
        });
        web.setDownloadListener((url, agent, disposition, type, size) -> download(url, null));
        worker.execute(() -> {
            try {
                // Clear only abandoned export staging files in this app's private cache.
                File[] old = getCacheDir().listFiles((dir, name) -> name.startsWith("sr-export-") || name.startsWith("sr-report-"));
                if (old != null) for (File file : old) file.delete();
                if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
                JSONObject info = new JSONObject(Python.getInstance().getModule("sehatraasta.android_runtime")
                        .callAttr("start", getFilesDir().getAbsolutePath(), getCacheDir().getAbsolutePath()).toString());
                origin = info.getString("origin");
                String cookie = "sr_device=" + info.getString("token") + "; Path=/; HttpOnly; SameSite=Strict";
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    CookieManager.getInstance().setCookie(origin, cookie, accepted -> {
                        if (!isFinishing() && !isDestroyed()) web.loadUrl(origin + "/");
                    });
                });
            } catch (Exception error) {
                runOnUiThread(() -> loading.setText(R.string.opening_failed));
            }
        });
    }

    private boolean isLocal(String url) {
        if (origin == null || url == null) return false;
        Uri uri = Uri.parse(url), base = Uri.parse(origin);
        return "http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost())
                && uri.getPort() == base.getPort() && uri.getUserInfo() == null;
    }

    private void message(String text) {
        runOnUiThread(() -> Toast.makeText(this, text, Toast.LENGTH_LONG).show());
    }

    private boolean isReportPage(String url) {
        if (!isLocal(url)) return false;
        Uri uri = Uri.parse(url);
        String path = uri.getPath();
        return path != null && (path.matches("/bundles/[^/]+/print")
                || (path.matches("/patients/[^/]+/print") && "yes".equals(uri.getQueryParameter("preview"))));
    }

    private void setPageBackground(String url) {
        int color = isReportPage(url) ? 0xffffffff : 0xfff2eee5;
        root.setBackgroundColor(color);
        web.setBackgroundColor(color);
    }

    public final class DeviceBridge {
        @JavascriptInterface public void scanQR(boolean image, String prompt) {
            runOnUiThread(() -> {
                if (!isLocal(web.getUrl()) || !"/lookup".equals(Uri.parse(web.getUrl()).getPath())) return;
                if (image) {
                    Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                            .setType("image/*");
                    try { startActivityForResult(pick, PICK_QR); }
                    catch (Exception error) { qrResult(null, "unavailable"); }
                } else {
                    try {
                        new IntentIntegrator(MainActivity.this).setDesiredBarcodeFormats(IntentIntegrator.QR_CODE)
                                .addExtra(Intents.Scan.SHOW_MISSING_CAMERA_PERMISSION_DIALOG, false)
                                .setBeepEnabled(false).setOrientationLocked(false)
                                .setPrompt(prompt == null ? "SehatRaasta QR" : prompt.substring(0, Math.min(200, prompt.length())))
                                .initiateScan();
                    } catch (Exception error) { qrResult(null, "unavailable"); }
                }
            });
        }
        @JavascriptInterface public void saveDownload(String url, String body) {
            runOnUiThread(() -> download(url, body));
        }
        @JavascriptInterface public void printDocument() {
            runOnUiThread(() -> {
                if (!isReportPage(web.getUrl())) return;
                web.evaluateJavascript("document.documentElement.dataset.reportReady==='yes'", ready -> {
                    if (!"true".equals(ready) || !isReportPage(web.getUrl()) || isFinishing() || isDestroyed()) return;
                    setPageBackground(web.getUrl());
                    PrintManager manager = (PrintManager) getSystemService(PRINT_SERVICE);
                    PrintAttributes attributes = new PrintAttributes.Builder()
                            .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                            .setColorMode(PrintAttributes.COLOR_MODE_COLOR)
                            .build();
                    manager.print("SehatRaasta visit history", web.createPrintDocumentAdapter("SehatRaasta visit history"), attributes);
                });
            });
        }
    }

    private void qrResult(String payload, String status) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed() || !isLocal(web.getUrl())) return;
            boolean tooLong = payload != null && payload.length() > 200;
            web.evaluateJavascript("window.srQRResult && window.srQRResult("
                    + (payload == null || tooLong ? "null" : JSONObject.quote(payload)) + "," + JSONObject.quote(tooLong ? "invalid" : status) + ")", null);
        });
    }

    private void download(String url, String body) {
        if (!isLocal(url) || (body != null && body.length() > 16384)) return;
        if (downloading || pendingDownload != null) { message("Finish saving the current file first."); return; }
        downloading = true;
        String cookie = CookieManager.getInstance().getCookie(origin);
        worker.execute(() -> {
            File staged = null;
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(url).openConnection();
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(60000);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("Cookie", cookie == null ? "" : cookie);
                if (body != null) {
                    connection.setRequestMethod("POST");
                    connection.setDoOutput(true);
                    connection.setRequestProperty("Origin", origin);
                    connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8");
                    try (OutputStream out = connection.getOutputStream()) { out.write(body.getBytes(StandardCharsets.UTF_8)); }
                }
                String disposition = connection.getHeaderField("Content-Disposition");
                if (connection.getResponseCode() != 200 || disposition == null || !disposition.startsWith("attachment"))
                    throw new IOException("Download unavailable");
                String type = connection.getContentType();
                String name = URLUtil.guessFileName(url, disposition, type);
                staged = File.createTempFile("sr-export-", ".tmp", getCacheDir());
                try (InputStream input = connection.getInputStream(); OutputStream output = new FileOutputStream(staged)) {
                    byte[] buffer = new byte[16384]; long total = 0; int count;
                    while ((count = input.read(buffer)) != -1) {
                        total += count;
                        if (total > MAX_DOWNLOAD) throw new IOException("File too large");
                        output.write(buffer, 0, count);
                    }
                }
                File ready = staged;
                runOnUiThread(() -> {
                    downloading = false;
                    pendingDownload = ready;
                    Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
                            .setType(type == null ? "application/octet-stream" : type.split(";")[0])
                            .putExtra(Intent.EXTRA_TITLE, name);
                    try { startActivityForResult(save, SAVE_FILE); }
                    catch (Exception error) { ready.delete(); pendingDownload = null; message("No save dialog is available."); }
                });
            } catch (Exception error) {
                if (staged != null) staged.delete();
                runOnUiThread(() -> downloading = false);
                message("Could not prepare the file. Reopen this page and try again.");
            } finally { if (connection != null) connection.disconnect(); }
        });
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        IntentResult scanned = IntentIntegrator.parseActivityResult(request, result, data);
        if (scanned != null) {
            boolean denied = data != null && data.getBooleanExtra(Intents.Scan.MISSING_CAMERA_PERMISSION, false);
            qrResult(scanned.getContents(), denied ? "unavailable" : scanned.getContents() == null ? "cancelled" : "success");
            return;
        }
        if (request == PICK_QR) {
            if (result != RESULT_OK || data == null || data.getData() == null) { qrResult(null, "cancelled"); return; }
            Uri selected = data.getData();
            worker.execute(() -> {
                try (InputStream input = getContentResolver().openInputStream(selected)) {
                    qrResult(QRImageDecoder.decode(input), "success");
                } catch (Exception error) { qrResult(null, "invalid"); }
            });
            return;
        }
        if (request == PICK_FILE && upload != null) {
            upload.onReceiveValue(result == RESULT_OK && data != null && data.getData() != null ? new Uri[]{data.getData()} : null);
            upload = null;
        } else if (request == SAVE_FILE && pendingDownload != null) {
            File file = pendingDownload; pendingDownload = null;
            if (result != RESULT_OK || data == null || data.getData() == null) { file.delete(); return; }
            Uri target = data.getData();
            worker.execute(() -> {
                try (InputStream input = new FileInputStream(file); OutputStream output = getContentResolver().openOutputStream(target, "wt")) {
                    if (output == null) throw new IOException("No destination");
                    byte[] buffer = new byte[16384]; int count;
                    while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
                    message("File saved.");
                } catch (Exception error) { message("The file could not be saved. Please try again."); }
                finally { file.delete(); }
            });
        }
    }

    @Override public void onBackPressed() {
        handleBack();
    }

    private void handleBack() {
        if (!isLocal(web.getUrl())) { finish(); return; }
        web.evaluateJavascript("Boolean(window.srDismissOverlay && window.srDismissOverlay())", dismissed -> {
            if (isFinishing() || isDestroyed() || "true".equals(dismissed)) return;
            if (web.canGoBack()) web.goBack(); else finish();
        });
    }

    @Override protected void onDestroy() {
        if (upload != null) upload.onReceiveValue(null);
        web.removeJavascriptInterface("SRAndroid");
        web.destroy();
        worker.shutdown();
        super.onDestroy();
    }
}
