$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$configPath = Join-Path $env:APPDATA 'IPhoneOtpSkill\config.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw '请先运行 Install.cmd。' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$addresses = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } |
    ForEach-Object { $_.IPv4Address.IPAddress } | Select-Object -Unique)
if ($addresses.Count -eq 0) { $addresses = @('请连接局域网') }
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form
$form.Text = 'iPhone OTP Skill · 手机配置'
$form.ClientSize = New-Object Drawing.Size(710,570)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = New-Object Drawing.Font('Microsoft YaHei UI',10)

function Add-Label([string]$text, [int]$y, [int]$height = 28) {
    $label = New-Object Windows.Forms.Label
    $label.Text = $text
    $label.Location = New-Object Drawing.Point(24,$y)
    $label.Size = New-Object Drawing.Size(660,$height)
    $form.Controls.Add($label)
}
function Add-Box([int]$y) {
    $box = New-Object Windows.Forms.TextBox
    $box.ReadOnly = $true
    $box.Location = New-Object Drawing.Point(24,$y)
    $box.Size = New-Object Drawing.Size(545,32)
    $form.Controls.Add($box)
    return $box
}
Add-Label '电脑端已配置。只需把下面两项填进 iPhone 快捷指令。' 22
Add-Label '电脑局域网 IP（有多个时选与手机同网段的地址）' 65
$ipChoice = New-Object Windows.Forms.ComboBox
$ipChoice.Location = New-Object Drawing.Point(24,96)
$ipChoice.Size = New-Object Drawing.Size(300,32)
$ipChoice.DropDownStyle = 'DropDownList'
$ipChoice.Items.AddRange([object[]]$addresses)
$form.Controls.Add($ipChoice)
Add-Label '推送 URL' 142
$urlBox = Add-Box 173
Add-Label 'Authorization（整段复制，包含 Bearer 和后面的空格）' 217
$authBox = Add-Box 248
$authBox.Text = 'Bearer ' + $config.phoneToken
Add-Label '健康检查 URL（手机 Safari 打开，应显示 ok: true）' 292
$healthBox = Add-Box 323
foreach ($pair in @(@($urlBox,173), @($authBox,248), @($healthBox,323))) {
    $button = New-Object Windows.Forms.Button
    $button.Text = '复制'
    $button.Location = [Drawing.Point]::new(584,([int]$pair[1] - 2))
    $button.Size = New-Object Drawing.Size(92,32)
    $button.Tag = $pair[0]
    $button.Add_Click({ [Windows.Forms.Clipboard]::SetText($this.Tag.Text) })
    $form.Controls.Add($button)
}
$ipChoice.Add_SelectedIndexChanged({
    $urlBox.Text = 'http://' + $ipChoice.SelectedItem + ':' + $config.port + '/api/sms'
    $healthBox.Text = 'http://' + $ipChoice.SelectedItem + ':' + $config.port + '/health'
})
$ipChoice.SelectedIndex = 0
Add-Label "手机：信息包含‘验证码’ → 获取 URL 内容 → POST → JSON。`r`n头部另加 Content-Type = application/json。`r`nJSON 键 message；值选触发卡片下方蓝色‘信息’。" 375 84
Add-Label '模型：使用 $iphone-otp 读取刚收到的验证码。' 470
$credit = New-Object Windows.Forms.LinkLabel
$credit.Text = '感谢 OtpBridge / OBW（csyxcsyx）提供手机推送方案与兼容协议'
$credit.Location = New-Object Drawing.Point(24,518)
$credit.Size = New-Object Drawing.Size(660,30)
$credit.Add_LinkClicked({ Start-Process 'https://github.com/csyxcsyx/OBW' })
$form.Controls.Add($credit)
[void]$form.ShowDialog()
