# 手机与电脑配置

## 已有 OtpBridge 的电脑

运行 `scripts/manage.ps1 -Action Install -MigrateOtpBridge -EnableStartup` 会复用本机 OtpBridge 的手机推送 Token 和端口，将接收工作切换到本项目后台程序。手机现有 URL、POST 请求体、Token 均无需改动。旧程序的设置与自启动命令备份到 `%APPDATA%\IPhoneOtpSkill\otpbridge-backup.json`，原 EXE 保留，可运行 `-Action Rollback` 恢复。

新程序没有 OtpBridge 的托盘窗口与自动复制；取码通过技能接口完成。后台程序随 Windows 用户登录启动。

## 新电脑

1. 解压 Windows x64 完整发布包，双击 `Install.cmd`。接收端与 CLI 的 EXE 都自包含运行时，不需要另装 Python。
2. 安装器自动复制到 Codex skills 目录、配置自启动与局域网规则，并显示手机配置窗口。
3. 用配置窗口的 URL 与 Authorization 填写手机。配置文件位于 `%APPDATA%\IPhoneOtpSkill\config.json`；`phoneToken` 用于手机，`readerToken` 仅供本地脚本。配置不要上传或放进技能包。
4. 如手机无法打开 `http://<电脑局域网IP>:18080/health`，以管理员 PowerShell 运行 `scripts/enable-lan.ps1`。规则只允许局域网手机推送端口，不开放读码端口。

## iPhone 快捷指令（已在这台手机验证的界面）

触发条件“信息 包含 验证码”；打开“自动化”，关闭“运行前确认”。如显示“配置‘发件人’启用此自动化”，点左侧“发件人”改为“信息”，然后设为“包含 验证码”，删掉重复条件。

添加“获取 URL 内容”：

| 项目 | 值 |
| --- | --- |
| URL | `http://<电脑局域网IP>:18080/api/sms` |
| 方法 | POST |
| Authorization 头部 | `Bearer ` 加 phoneToken，Bearer 后有一个空格 |
| Content-Type 头部 | `application/json` |
| 请求体 | JSON |
| JSON 键 | `message`，恰好 7 个字母，无前后空格 |
| JSON 值 | 触发卡片下方蓝色“💬 信息”输出变量 |

此手机界面不用再找变量“属性”，也不要选择顶部“输入快捷指令的信息”。`sender` 可选；未提供时无法按号码筛选。服务名称筛选直接匹配短信正文，例如 `--contains 支付宝`。

这是 iOS 自动化主动推送新短信，不是远程读取 iPhone 短信数据库。新短信需命中自动化条件；手机与电脑在同一可互通的局域网、电脑开机且未休眠。现有条件只匹配“验证码”，纯英文 code 短信需另建相应自动化。

## 排查

- `config_missing_or_invalid`：先运行安装命令，同一 Windows 用户执行脚本与接收端。
- `receiver_unavailable`：执行 `manage.ps1 -Action Start`；检查端口是否被占用。不要输出配置文件原文排查。
- `/health` 从手机可达，但 `message is required`：检查键末尾空格和短信变量；网络已经通了。
- `timeout` / `pending`：当前还没有符合筛选的新码；核对关键词和位数。同一 ticket 可继续等，总共 180 秒。
- `ticket_expired_or_unknown`：超过 180 秒或接收端重启；这一轮结束，按当前网站流程决定是否重新获取，不自动循环发短信。
- `ambiguous`：匹配多个短信，不猜哪条正确。按已知服务名称用 `read --contains ... --max-age ...` 缩小到一条，或让用户澄清正在验证哪个服务。
- `code_not_found` / `ambiguous_code_in_message`：没有找到 4–8 位码，或一条短信中有多个候选。不能编造验证码。

接收内存最多保留 50 条、最长 5 分钟；全文仅用于服务筛选，不向模型输出。程序退出后记录消失。`receivedAtUtc` 是电脑接受推送的时间，不代表运营商送达时间。已取码标为 consumed，其他请求不再取得；同一个 ticket 的重试会幂等返回该码并标记 `replayed: true`。
