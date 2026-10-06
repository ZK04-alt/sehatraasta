# PowerShell only. Configure the four SR_UPLOAD_* variables privately first.
$ErrorActionPreference = 'Stop'
foreach ($name in @('SR_UPLOAD_KEYSTORE', 'SR_UPLOAD_STORE_PASSWORD', 'SR_UPLOAD_KEY_ALIAS', 'SR_UPLOAD_KEY_PASSWORD')) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        throw "Missing $name. A Google Play upload must not use the debug signing key."
    }
}
if (-not (Test-Path -LiteralPath $env:SR_UPLOAD_KEYSTORE -PathType Leaf)) {
    throw 'The configured upload keystore was not found.'
}
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    & './android/gradlew.bat' -p android bundlePlay lintPlay
    if ($LASTEXITCODE -ne 0) { throw 'Play build or lint failed.' }
    $buildRoot = if ($env:SR_ANDROID_BUILD_DIR) { $env:SR_ANDROID_BUILD_DIR } else { Join-Path $projectRoot 'android/app/build' }
    $bundle = Join-Path $buildRoot 'outputs/bundle/play/app-play.aab'
    $outputFolder = Join-Path $projectRoot 'output/google-play'
    New-Item -ItemType Directory -Path $outputFolder -Force | Out-Null
    Copy-Item -LiteralPath $bundle -Destination (Join-Path $outputFolder 'SehatRaasta-1.5-signed.aab')
    Write-Output 'Signed Play bundle built. Verify its upload certificate before submission.'
} finally {
    Pop-Location
}
