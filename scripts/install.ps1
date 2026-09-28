param([switch]$MigrateOtpBridge, [switch]$NoUI, [switch]$SkipFirewall)
$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
foreach ($requiredBinary in @('PhoneOtp.exe','PhoneOtpReceiver.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot ('bin\' + $requiredBinary)) -PathType Leaf)) {
        throw 'This is a source checkout. Download iphone-jiema-v*-windows-x64.zip from GitHub Releases, or run scripts/build_release.py first.'
    }
}
$codexBase = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$installRoot = [IO.Path]::GetFullPath((Join-Path $codexBase 'skills\iphone-otp'))
$existingOtpBridge = Test-Path -LiteralPath (Join-Path $env:APPDATA 'OtpBridge\config.json')
$alreadyConfigured = Test-Path -LiteralPath (Join-Path $env:APPDATA 'IPhoneOtpSkill\config.json')
if ($existingOtpBridge -and -not $alreadyConfigured -and -not $MigrateOtpBridge) {
    if ($NoUI) { throw 'OtpBridge exists. Use -MigrateOtpBridge to keep the current phone settings.' }
    Add-Type -AssemblyName System.Windows.Forms
    $answer = [Windows.Forms.MessageBox]::Show(
        '发现已有 OtpBridge。是否迁移原端口和 Token？手机无需改动，原程序设置会备份。选择否将退出安装，保持原配置。',
        'iPhone OTP Skill', 'YesNo', 'Question')
    if ($answer -ne 'Yes') { return }
    $MigrateOtpBridge = $true
}
if ($sourceRoot -ne $installRoot) {
    $installedManager = Join-Path $installRoot 'scripts\manage.ps1'
    if (Test-Path -LiteralPath $installedManager) { & $installedManager -Action Stop | Out-Null }
    New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
    $sourcePrefix = $sourceRoot.TrimEnd('\') + '\'
    foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
        if ($file.FullName.Substring($sourcePrefix.Length) -match '(^|[\\/])(\.git|\.github|\.build|dist|__pycache__)([\\/]|$)' -or $file.Extension -eq '.pyc') { continue }
        $relative = $file.FullName.Substring($sourcePrefix.Length)
        $destination = Join-Path $installRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
    }
}
& (Join-Path $installRoot 'scripts\manage.ps1') -Action Install -MigrateOtpBridge:$MigrateOtpBridge -EnableStartup
if ($LASTEXITCODE -ne 0) { throw 'Receiver installation failed.' }
$firewallReady = $false
if (-not $SkipFirewall) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    $lanScript = Join-Path $installRoot 'scripts\enable-lan.ps1'
    $installedExe = Join-Path $installRoot 'bin\PhoneOtpReceiver.exe'
    $localConfig = Get-Content -LiteralPath (Join-Path $env:APPDATA 'IPhoneOtpSkill\config.json') -Raw | ConvertFrom-Json
    $phonePort = [int]$localConfig.port
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        & $lanScript -ReceiverPath $installedExe -Port $phonePort
        $firewallReady = $true
    } else {
        try {
            $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $lanScript + '" -ReceiverPath "' + $installedExe + '" -Port ' + $phonePort
            $elevated = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -PassThru -Wait
            $firewallReady = $elevated.ExitCode -eq 0
        } catch { Write-Warning '未完成防火墙配置。如手机无法连接，请以管理员权限运行 scripts\enable-lan.ps1。' }
    }
}
Write-Output ('Installed: ' + $installRoot)
Write-Output ('LAN firewall configured: ' + $firewallReady)
if (-not $NoUI) { & (Join-Path $installRoot 'scripts\show-setup.ps1') }
