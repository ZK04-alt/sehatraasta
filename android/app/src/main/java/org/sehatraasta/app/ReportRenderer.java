package org.sehatraasta.app;

import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.pdf.PdfRenderer;
import android.os.ParcelFileDescriptor;
import android.util.Base64;
import org.json.JSONArray;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;

/** On-device PDF rendering, including older Android System WebView versions. */
public final class ReportRenderer {
    public static String render(String encoded, String directory) throws Exception {
        byte[] content = Base64.decode(encoded, Base64.DEFAULT);
        if (content.length > 5242880) throw new IllegalArgumentException("file too large");
        File temporary = File.createTempFile("sr-report-", ".pdf", new File(directory));
        try {
            try (FileOutputStream out = new FileOutputStream(temporary)) { out.write(content); }
            JSONArray images = new JSONArray();
            int encodedSize = 0;
            try (ParcelFileDescriptor file = ParcelFileDescriptor.open(temporary, ParcelFileDescriptor.MODE_READ_ONLY);
                 PdfRenderer renderer = new PdfRenderer(file)) {
                if (renderer.getPageCount() < 1 || renderer.getPageCount() > 60) throw new IllegalArgumentException("page limit");
                for (int number = 0; number < renderer.getPageCount(); number++) {
                    try (PdfRenderer.Page page = renderer.openPage(number)) {
                        double scale = Math.min(2.0, 1600.0 / Math.max(page.getWidth(), page.getHeight()));
                        Bitmap bitmap = Bitmap.createBitmap(Math.max(1, (int)(page.getWidth()*scale)), Math.max(1, (int)(page.getHeight()*scale)), Bitmap.Config.ARGB_8888);
                        try {
                            bitmap.eraseColor(Color.WHITE);
                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_PRINT);
                            ByteArrayOutputStream out = new ByteArrayOutputStream();
                            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
                            String image = "data:image/png;base64," + Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
                            encodedSize += image.length();
                            if (encodedSize > 16777216) throw new IllegalArgumentException("choose fewer document pages");
                            images.put(image);
                        } finally { bitmap.recycle(); }
                    }
                }
            }
            return images.toString();
        } finally { temporary.delete(); }
    }
}
