#Requires -RunAsAdministrator
param([string]$ReceiverPath, [int]$Port = 0)
$ErrorActionPreference = 'Stop'
if (-not $ReceiverPath) { $ReceiverPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'bin\PhoneOtpReceiver.exe' }
$receiverExe = (Resolve-Path -LiteralPath $ReceiverPath).Path
if ($Port -eq 0) {
    $configPath = Join-Path $env:APPDATA 'IPhoneOtpSkill\config.json'
    $settings = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $Port = [int]$settings.port
}
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Invalid phone-push port.' }
$ruleName = 'IPhoneOtpSkill-LAN'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) { $existing | Remove-NetFirewallRule }
New-NetFirewallRule -Name $ruleName -DisplayName 'iPhone OTP Skill - phone push on local subnet' `
    -Direction Inbound -Action Allow -Enabled True -Profile Any -Protocol TCP `
    -LocalPort $Port -RemoteAddress LocalSubnet -Program $receiverExe -EdgeTraversalPolicy Block | Out-Null
Write-Output 'Phone-push LAN rule enabled. The reader API stays bound to loopback.'
