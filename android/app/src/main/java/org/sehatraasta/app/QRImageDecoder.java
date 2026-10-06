package org.sehatraasta.app;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import com.google.zxing.*;
import com.google.zxing.common.HybridBinarizer;
import com.google.zxing.qrcode.QRCodeReader;
import java.io.*;

/** Bounded image decoding; no network, image upload or retained camera frames. */
public final class QRImageDecoder {
    public static String decode(InputStream stream) throws Exception {
        if (stream == null) throw new IOException("No image");
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        byte[] chunk = new byte[16384]; int count;
        while ((count = stream.read(chunk)) != -1) {
            if (bytes.size() + count > 5 * 1024 * 1024) throw new IOException("Image too large");
            bytes.write(chunk, 0, count);
        }
        byte[] content = bytes.toByteArray();
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(content, 0, content.length, options);
        if (options.outWidth <= 0 || options.outHeight <= 0) throw new IOException("Invalid image");
        options.inSampleSize = 1;
        while (Math.max(options.outWidth, options.outHeight) / options.inSampleSize > 2048) options.inSampleSize *= 2;
        options.inJustDecodeBounds = false;
        Bitmap bitmap = BitmapFactory.decodeByteArray(content, 0, content.length, options);
        if (bitmap == null) throw new IOException("Invalid image");
        try {
            int width = bitmap.getWidth(), height = bitmap.getHeight();
            int[] pixels = new int[width * height];
            bitmap.getPixels(pixels, 0, width, 0, 0, width, height);
            BinaryBitmap qr = new BinaryBitmap(new HybridBinarizer(new RGBLuminanceSource(width, height, pixels)));
            String value = new QRCodeReader().decode(qr).getText();
            if (value.length() > 200) throw new IOException("Unsupported QR");
            return value;
        } finally { bitmap.recycle(); }
    }
}
