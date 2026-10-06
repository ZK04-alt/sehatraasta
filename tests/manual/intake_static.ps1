# Read-only source checks; generated review artifacts go under docs/testing.
# Run from the repository root. This script never opens instance data.
$ErrorActionPreference = 'Stop'
$taskWebRoot = 'src/sehatraasta/web'
$taskChecks = @{
    'inline script blocks' = '<script\b(?![^>]*\bsrc\s*=)[^>]*>'
    'inline style blocks' = '<style\b'
    'inline event handlers' = '\bon[a-z]+\s*='
    'style attributes' = '(?<![\w-])style\s*='
    'external asset references' = '(?:src|href)\s*=\s*["''](?:https?:)?//|url\(\s*["'']?(?:https?:)?//|@import\b'
    'obsolete app.local references' = 't\(["'']app\.local["'']\)'
}
$taskResults = @()
foreach ($taskCheck in $taskChecks.GetEnumerator()) {
    $taskHits = @(rg -n -i --pcre2 --no-ignore $taskCheck.Value "$taskWebRoot/templates" "$taskWebRoot/static")
    if ($LASTEXITCODE -gt 1) { throw "Search failed: $($taskCheck.Key)" }
    $taskResults += [pscustomobject]@{check=$taskCheck.Key; hits=$taskHits.Count; matches=$taskHits}
    if ($taskHits.Count) { throw "Unexpected source hit: $($taskCheck.Key): $taskHits" }
}
$taskAfter = Get-Content -LiteralPath "$taskWebRoot/messages.py" | Where-Object { $_ -match "'app.notice':" }
# SHA-256 of the exact pre-edit UTF-8 app.notice source line (no line terminator).
# Recorded from tmp/intake-before-messages.py, not calculated from edited content.
$taskExpected = '7fc1c7e84c6b2bf477ea6ef29cf3e5ea3a1b2fd23827997860db59ea559899b1'
$taskDigest = [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData([System.Text.Encoding]::UTF8.GetBytes($taskAfter))).ToLowerInvariant()
if ($taskDigest -cne $taskExpected) { throw 'Protected notice changed' }
$taskResults += [pscustomobject]@{check='protected app.notice matches pre-edit UTF-8 text'; hits=0; matches=@()}

# Search the whole repository, including ignored project text, not dependencies,
# binary documents, caches, Git internals, or the protected real instance folder.
$taskWording = @(rg -n -i --no-ignore --hidden --json -e "t\('app\.local'\)" -e 'Local device only' -e 'Fictional' -e 'fictional patient' -e 'fictional case' . --glob '!.git' --glob '!.venv' --glob '!instance' --glob '!.pytest_cache' --glob '!**/__pycache__' --glob '!**/node_modules' --glob '!*.pyc' --glob '!*.pdf' --glob '!*.png' --glob '!*.sqlite*' --glob '!docs/testing/intake-wording.json' --glob '!docs/testing/intake-static.json')
if ($LASTEXITCODE -gt 1) { throw 'Repository wording search failed' }
$taskClassified = @()
foreach ($taskLine in $taskWording) {
    $taskItem = $taskLine | ConvertFrom-Json
    if ($taskItem.type -ne 'match') { continue }
    $taskPath = $taskItem.data.path.text.Replace('\','/').TrimStart('.','/')
    $taskText = $taskItem.data.lines.text.TrimEnd()
    $taskCategory = switch -Regex ($taskPath) {
        '^tmp/' { 'Retain: historical snapshot, synthetic output, or unrelated research artifact'; break }
        '^tests/' { 'Retain: synthetic fixture, test assertion, or review tooling'; break }
        '^(learning/|learning-labs/)' { 'Retain: learning material or explicitly synthetic practice lab'; break }
        '^(docs/|README.md$|SAFETY.md$)' { 'Retain: safety guidance, synthetic scenario, historical design, or review evidence'; break }
        '^src/sehatraasta/web/messages.py$' { 'Retain: protected app.notice safety warning'; break }
        '^src/sehatraasta/web/templates/policy.html$' { 'Retain: deliberate synthetic-use policy'; break }
        '^src/sehatraasta/presentation/catalogs.py$' { 'Retain: synthetic confirmation or practice-lab guidance'; break }
        '^src/sehatraasta/phase_commands.py$' { 'Retain: synthetic upload confirmation'; break }
        '^src/sehatraasta/cli.py$' { 'Retain: explicit fictional-result instruction; patient labels were neutralized'; break }
        default { 'REVIEW REQUIRED' }
    }
    $taskClassified += [pscustomobject]@{path=$taskPath; line=$taskItem.data.line_number; classification=$taskCategory; text=$taskText}
}
if ($taskClassified.classification -contains 'REVIEW REQUIRED') { throw 'Unclassified wording hit' }
$taskClassified | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 docs/testing/intake-wording.json
$taskResults | ConvertTo-Json -Depth 4 | Set-Content -Encoding utf8 docs/testing/intake-static.json
$taskResults | Format-Table check,hits -AutoSize
Write-Output "Classified $($taskClassified.Count) matching lines; no unclassified hits."
