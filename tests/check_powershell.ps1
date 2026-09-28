$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$failures = @()
Get-ChildItem -LiteralPath (Join-Path $root 'scripts') -Filter '*.ps1' | ForEach-Object {
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$tokens,[ref]$errors) | Out-Null
    if ($errors) { $failures += $errors }
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -ge 3 -and ($bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191)) {
        if ([Text.Encoding]::UTF8.GetString($bytes) -match '[^\x00-\x7f]') {
            throw ('Non-ASCII PowerShell script must have a UTF-8 BOM: ' + $_.Name)
        }
    }
}
if ($failures) { $failures | ForEach-Object { Write-Error $_.Message }; exit 1 }
Write-Output 'Windows PowerShell syntax and encoding checks passed.'
