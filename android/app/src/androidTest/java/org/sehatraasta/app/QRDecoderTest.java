package org.sehatraasta.app;

import android.graphics.Bitmap;
import com.google.zxing.BarcodeFormat;
import com.journeyapps.barcodescanner.BarcodeEncoder;
import java.io.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class QRDecoderTest {
    @Test public void decodesQRWithoutNetwork() throws Exception {
        String payload = "{\"id\":\"0123456789abcdef0123456789abcdef\",\"v\":1,\"check\":\"0123456789abcdef\"}";
        Bitmap image = new BarcodeEncoder().encodeBitmap(payload, BarcodeFormat.QR_CODE, 640, 640);
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        image.compress(Bitmap.CompressFormat.PNG, 100, bytes);
        assertEquals(payload, QRImageDecoder.decode(new ByteArrayInputStream(bytes.toByteArray())));
        image.recycle();
    }

    @Test public void rejectsNonImage() throws Exception {
        try {
            QRImageDecoder.decode(new ByteArrayInputStream(new byte[]{1, 2, 3}));
            fail("Invalid image accepted");
        } catch (IOException expected) { }
    }

    @Test public void rejectsOversizedImage() throws Exception {
        try {
            QRImageDecoder.decode(new ByteArrayInputStream(new byte[5 * 1024 * 1024 + 1]));
            fail("Oversized image accepted");
        } catch (IOException expected) { }
    }
}
