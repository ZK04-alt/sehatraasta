# SehatRaasta for Android

An offline Android application using SR's existing forms, validation, SQLite storage and document services. No computer or hosted website is needed after installation. Data is stored in the application's private storage, independently of desktop data. There is no automatic synchronization.

## Install

Version 1.5 fixes the report's beige surroundings, keeps A4 layout separate from
phone preview layout, and adds clear medicine/test labels and patient identity
on continuation and document pages. **Patients → patient → Choose visits for PDF**: select visits,
include uploaded reports/photos, preview, then print or save. Blank fields are
omitted; costs are optional. **Remove visit** keeps the patient's other visits.
**Menu → How sharing works** explains PDFs, QR and passport transfer.
Verification reports and Google Play preparation notes are retained locally.
Google Play distribution requires a protected upload key and the normal store review process; the local APK is not a Play release.

Copy `output/android/SehatRaasta.apk` from the repository to a 64-bit Android phone running Android 7 or later. Open the APK and allow installation from that file source when Android asks. Open **SehatRaasta** from the launcher. A recent Android System WebView is recommended.

Use **Patients → patient → Remove patient** to remove a patient and all their bundles and stored attachments. Use **Backup** to save a copy through Android's document picker. **Restore** checks a backup first, then opens the restored dataset after confirmation. The previous dataset remains as a separate private copy. Exports and printouts are separate copies too.

Attachments use Android's file picker. Downloads, exports and backups use its save dialog. Printable summaries use the Android print service, including Save as PDF when available. Uninstalling the app removes its private records; save a backup first if you need them.

## Build

Requirements: JDK 17, Gradle 8.13, Android SDK platform 36 and build tools 36.0.0, Python 3.12. Set `JAVA_HOME`, `ANDROID_HOME` and optionally `SR_BUILD_PYTHON` (the path to the build machine's Python executable).

From `android/`:

```bash
./gradlew assembleRelease
```

The APK is `app/build/outputs/apk/release/app-release.apk`. It includes ARM64 phone and x86_64 emulator support. The local release build is not debuggable and uses the local Android debug signing key so it can be installed directly. Keep the same signing key for subsequent updates. Store distribution needs a dedicated protected release key and the normal publication process; this project does not publish automatically.

The separate `play` build type never falls back to the debug key. Without upload-key
configuration, `./gradlew bundlePlay` produces an unsigned preparation bundle.
With `SR_UPLOAD_KEYSTORE`, `SR_UPLOAD_STORE_PASSWORD`, `SR_UPLOAD_KEY_ALIAS` and
`SR_UPLOAD_KEY_PASSWORD` configured privately, `scripts/build_play_release.ps1` (PowerShell only) builds a signed bundle.
Do not put key passwords in this repository or in chat.

## Design and permissions

The APK embeds Python through [Chaquopy](https://chaquo.com/chaquopy/doc/current/android.html). A private loopback server serves SR to the embedded WebView. A random, process-specific HTTP-only cookie is required before the server handles any request. Only that loopback origin is allowed in the WebView; external navigation and file access are blocked. The `INTERNET` permission allows this on-device connection. The app does not require internet connectivity or send records to a server.

Database and attachments are in private app storage. Automatic Android backup is disabled. No broad storage, contacts or location permission is requested. Camera permission is requested only when the user starts the QR scanner. The bundled scanner works without downloading a model or using internet. Reading a saved QR image uses the document picker and needs no camera permission. Explicit file selection and saving use the system document picker. Access logs do not record patient paths or form contents. As on desktop, there is no application login or extra database encryption.

## Referral passports (version 1.1)

Open a referral and choose **History and referral notes** to record reported history, allergies, the referral reason, receiving department and next visit date. Unknown values stay blank and display as **Not recorded**. This is not a clinical interpretation or allergy assessment.

The print view includes a QR at the top. **Local lookup** supports camera scanning, saved-image scanning and manual code entry. The QR contains a random reference only, not health details. It opens a record already on that device; it is not a public link or a portable medical record by itself.

To use a referral on another phone, open **Take this referral to another device**, confirm permission and save its ZIP. Transfer that file through an approved offline method. On the other phone choose **Receive a referral**, check the patient, reselect the same file and choose **Add this referral**. This adds a separate patient copy without overwriting existing records. The original printed QR then opens that copy. Repeated import of the same QR is rejected. This is not automatic synchronisation.

The single-referral transfer limit is 50 MiB of expanded data, with the existing 5 MiB per-document limit. ZIPs, PDFs and backups are not encrypted by the app. Keep exported copies protected and remove them separately when no longer needed. Use fictional records for testing; clinical and real-patient readiness require separate review.

## Check

Run the repository's Python tests and `./gradlew lintRelease`. To test on a connected emulator or phone, run `./gradlew connectedDebugAndroidTest`. Instrumentation uses an isolated test application ID and temporary records; it does not use the installed release application's data.

The native file-dialog checks use Android 10+ MediaStore APIs. File export/import, Save as PDF and restart checks passed on an offline Android 11 emulator. Selecting a saved QR image in the separate system provider remains unresolved in automation. The diagnostic argument below tests the real QR image-result handler with a real image URI, but bypasses the image-selection UI. It does not substitute for checking that UI on a phone. Build and install the debug app and Android test APK, then run these separately:

```bash
adb shell am instrument -w -r -e qrImageResultOnly true -e class org.sehatraasta.app.OfflineFlowTest#aCreateSaveAndRestoreOffline org.sehatraasta.app.test.test/androidx.test.runner.AndroidJUnitRunner
adb shell am force-stop org.sehatraasta.app.test
adb shell am instrument -w -r -e class org.sehatraasta.app.OfflineFlowTest#bReopenAndRemoveSavedPatient org.sehatraasta.app.test.test/androidx.test.runner.AndroidJUnitRunner
```

Both invocations must report `OK`. The second deliberately depends on the first test's saved dataset. Native tests leave synthetic exports in the emulator's Downloads folder for inspection. Actual phone, printer and file-provider behavior can differ; use non-sensitive examples when checking another device.
