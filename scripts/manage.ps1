param(
    [ValidateSet('Install','Start','Stop','Status','Rollback')][string]$Action = 'Status',
    [switch]$MigrateOtpBridge,
    [switch]$EnableStartup
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
$receiverExe = Join-Path $skillRoot 'bin\PhoneOtpReceiver.exe'
$dataDirectory = Join-Path $env:APPDATA 'IPhoneOtpSkill'
$configFile = Join-Path $dataDirectory 'config.json'
$backupFile = Join-Path $dataDirectory 'otpbridge-backup.json'
$oldConfigFile = Join-Path $env:APPDATA 'OtpBridge\config.json'
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

function Get-Settings {
    if (-not (Test-Path -LiteralPath $configFile)) { throw 'Receiver is not configured. Run Install first.' }
    return Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
}

function Get-ReceiverHealth {
    try {
        $config = Get-Settings
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$($config.readerPort)/health" -TimeoutSec 2
        return $health.app -eq 'IPhoneOtpSkill' -and $health.role -eq 'reader'
    } catch { return $false }
}

function Stop-OwnReceiver {
    $resolvedExe = [IO.Path]::GetFullPath($receiverExe)
    $processes = @(Get-Process -Name PhoneOtpReceiver -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and [IO.Path]::GetFullPath($_.Path) -eq $resolvedExe })
    foreach ($process in $processes) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 300
}

function Start-OwnReceiver {
    if (Get-ReceiverHealth) { return }
    if (-not (Test-Path -LiteralPath $receiverExe -PathType Leaf)) { throw 'PhoneOtpReceiver.exe is missing.' }
    Get-Settings | Out-Null
    Start-Process -FilePath $receiverExe -ArgumentList @('--config', ('"' + $configFile + '"')) -WindowStyle Hidden | Out-Null
    for ($attempt = 0; $attempt -lt 25; $attempt++) {
        Start-Sleep -Milliseconds 200
        if (Get-ReceiverHealth) { return }
    }
    throw 'Receiver failed to start. Check whether either configured port is occupied.'
}

function New-Token {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
}

function Start-PreviousReceiver([string]$commandLine) {
    if ([string]::IsNullOrWhiteSpace($commandLine)) { return }
    if ($commandLine -notmatch '^(?:"([^"]+)"|(\S+))(?:\s+(.*))?$') { throw 'Could not parse saved OtpBridge startup command.' }
    $fileName = if ($Matches[1]) { $Matches[1] } else { $Matches[2] }
    $arguments = $Matches[3]
    $launch = @{ FilePath = $fileName; WindowStyle = 'Hidden' }
    if (-not [string]::IsNullOrWhiteSpace($arguments)) { $launch.ArgumentList = $arguments }
    Start-Process @launch | Out-Null
}

if ($Action -eq 'Install') {
    New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
    # Restrict this directory containing tokens/backups to the current user and SYSTEM.
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls.exe $dataDirectory /inheritance:r /grant:r "*$($currentSid):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not restrict local configuration permissions.' }
    if (-not (Test-Path -LiteralPath $configFile)) {
        $phoneToken = New-Token
        $ingestPort = 18080
        if ($MigrateOtpBridge) {
            if (-not (Test-Path -LiteralPath $oldConfigFile)) { throw 'Existing OtpBridge config was not found.' }
            $oldSettingsText = Get-Content -LiteralPath $oldConfigFile -Raw
            $oldSettings = $oldSettingsText | ConvertFrom-Json
            $phoneToken = $oldSettings.apiToken
            $ingestPort = [int]$oldSettings.port
            if ([string]::IsNullOrWhiteSpace($phoneToken)) { throw 'Existing phone token is empty.' }
            $startupValue = (Get-ItemProperty -LiteralPath $runKey -Name OtpBridge -ErrorAction SilentlyContinue).OtpBridge
            $previousLaunch = $startupValue
            if (-not $previousLaunch) {
                $previousProcess = Get-Process -Name OtpBridge -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($previousProcess -and $previousProcess.Path) { $previousLaunch = '"' + $previousProcess.Path + '"' }
            }
            if (-not (Test-Path -LiteralPath $backupFile)) {
                [ordered]@{ configText = $oldSettingsText; startup = $startupValue; launch = $previousLaunch } |
                    ConvertTo-Json | Set-Content -LiteralPath $backupFile -Encoding UTF8
            }
        }
        $readerPort = 18082
        if ($readerPort -eq $ingestPort) { $readerPort = 18083 }
        [ordered]@{ port = $ingestPort; readerPort = $readerPort; phoneToken = $phoneToken; readerToken = (New-Token) } |
            ConvertTo-Json | Set-Content -LiteralPath $configFile -Encoding UTF8
    }
    if ($MigrateOtpBridge) {
        if (-not (Test-Path -LiteralPath $backupFile)) { throw 'Migration backup is missing; refusing to change existing receiver.' }
        $config = Get-Settings
        $listener = @(Get-NetTCPConnection -State Listen -LocalPort $config.port -ErrorAction SilentlyContinue)
        foreach ($ownerId in @($listener.OwningProcess | Select-Object -Unique)) {
            if (-not $ownerId) { continue }
            $owner = Get-Process -Id $ownerId -ErrorAction Stop
            if ($owner.ProcessName -eq 'OtpBridge') {
                Stop-Process -Id $owner.Id -Force
            } elseif ($owner.ProcessName -ne 'PhoneOtpReceiver') {
                throw 'The phone port is used by a different program; it was not stopped.'
            }
        }
        $oldSettings = Get-Content -LiteralPath $oldConfigFile -Raw | ConvertFrom-Json
        $oldSettings.startWithWindows = $false
        $oldSettings.autoCopy = $false
        $oldSettings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $oldConfigFile -Encoding UTF8
        Remove-ItemProperty -LiteralPath $runKey -Name OtpBridge -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }
    try {
        Start-OwnReceiver
    } catch {
        if ($MigrateOtpBridge -and (Test-Path -LiteralPath $backupFile)) {
            $saved = Get-Content -LiteralPath $backupFile -Raw | ConvertFrom-Json
            $saved.configText | Set-Content -LiteralPath $oldConfigFile -Encoding UTF8
            if ($saved.startup) { Set-ItemProperty -LiteralPath $runKey -Name OtpBridge -Value $saved.startup }
            Stop-OwnReceiver
            $previousLaunch = if ($saved.launch) { $saved.launch } else { $saved.startup }
            Start-PreviousReceiver $previousLaunch
        }
        throw
    }
    if ($EnableStartup) {
        if (-not (Test-Path -LiteralPath $runKey)) { New-Item -Path $runKey | Out-Null }
        Set-ItemProperty -LiteralPath $runKey -Name IPhoneOtpSkill -Value ('"' + $receiverExe + '" --config "' + $configFile + '"')
    }
} elseif ($Action -eq 'Start') {
    Start-OwnReceiver
} elseif ($Action -eq 'Stop') {
    Stop-OwnReceiver
} elseif ($Action -eq 'Rollback') {
    if (-not (Test-Path -LiteralPath $backupFile)) { throw 'No OtpBridge migration backup exists.' }
    Stop-OwnReceiver
    Remove-ItemProperty -LiteralPath $runKey -Name IPhoneOtpSkill -ErrorAction SilentlyContinue
    $saved = Get-Content -LiteralPath $backupFile -Raw | ConvertFrom-Json
    $saved.configText | Set-Content -LiteralPath $oldConfigFile -Encoding UTF8
    if ($saved.startup) {
        Set-ItemProperty -LiteralPath $runKey -Name OtpBridge -Value $saved.startup
    }
    $previousLaunch = if ($saved.launch) { $saved.launch } else { $saved.startup }
    Start-PreviousReceiver $previousLaunch
}

$ready = Get-ReceiverHealth
$config = if (Test-Path -LiteralPath $configFile) { Get-Settings } else { $null }
[ordered]@{ ok = $ready; app = 'IPhoneOtpSkill'; port = $config.port; readerPort = $config.readerPort; clipboardUsed = $false } | ConvertTo-Json -Compress
if ($Action -in @('Install','Start','Status') -and -not $ready) { exit 1 }
