# iphone-jiema · iPhone 验证码 Skill

**让本地大模型直接获取 iPhone 推送的验证码，日常复制粘贴不受影响。**

[下载 Windows 安装包](https://github.com/cxm947/iphone-jiema/releases/latest) · [手机 3 步教程](手机端极简教程.md) · [技能入口](SKILL.md)

仓库名称是 `iphone-jiema`，技能调用名是 **`$iphone-otp`**。

感谢 **[OtpBridge / OBW](https://github.com/csyxcsyx/OBW)** 及作者 **[csyxcsyx](https://github.com/csyxcsyx)** 提供 iPhone 快捷指令向 Windows 推送验证码的方案。本项目在这一思路上增加大模型读码接口、等待票据与取用管理，并兼容其 `/api/sms` 手机请求格式。我们使用独立编写的接收端，**不是 OtpBridge 官方版本**。详见 [来源与署名](NOTICE.md)。

```text
iPhone 收到短信
    ↓ 快捷指令自动 POST
Windows 接收端（内存保留最多 5 分钟）
    ↓ 仅本机可访问的读码接口
Skill → 大模型 → 当前网站验证码输入框
```

## 电脑端：第一次使用

适用于 Windows 10/11 x64 + iPhone，手机 Wi-Fi 与电脑有线或 Wi-Fi 接入同一可互通局域网。

1. 从 **[Releases](https://github.com/cxm947/iphone-jiema/releases)** 下载 `iphone-jiema-v版本号-windows-x64.zip`，解压后双击 **`Install.cmd`**。GitHub 的“Code → Download ZIP”只有源码，不包含 EXE。
2. 安装器会将技能复制到 `%USERPROFILE%\.codex\skills\iphone-otp`（设有 CODEX_HOME 时使用该目录），启动后台接收端并设为随用户登录启动。为放行手机推送，系统可能弹出管理员确认。
3. 配置窗口会显示**推送 URL**和 **Authorization**，照着 [手机端极简教程](手机端极简教程.md) 填入 iPhone。
4. 在新的 Codex 任务中说：**“用 $iphone-otp 帮我获取验证码并完成当前登录。”**

电脑端无需另装 Python、.NET 或 OtpBridge。用其他本地大模型客户端时，导入该技能目录，并让客户端能运行其中的 `bin/PhoneOtp.exe`。手机、接收端、客户端必须指向同一台电脑。

> 已安装 OtpBridge？安装器会询问是否迁移。选择迁移将复用原端口和 Token，手机无需重新配置；原程序与设置备份保留，可恢复。新接收端专注模型取码，不包含原来的托盘通知窗口。

## 手机端：只配置一次

打开 **[手机端极简教程](手机端极简教程.md)**。双击 `Setup.cmd` 可再次打开本机配置窗口。收到第一条真实验证码后，让模型读码完成验证即可。

## 模型可用命令

```powershell
& "<安装目录>\bin\PhoneOtp.exe" status
& "<安装目录>\bin\PhoneOtp.exe" arm --contains "服务名称" --length 6
# 用返回的 ticket，先在网站发送短信，再等待：
& "<安装目录>\bin\PhoneOtp.exe" wait --ticket "实际返回的 ticket" --timeout 30
# 若短信已经收到：
& "<安装目录>\bin\PhoneOtp.exe" read --contains "服务名称" --max-age 120
```

有多个候选码时不会猜测。不同任务可按服务名称筛选；取用标记防止被另一个任务重复领取。原始短信不落盘，API 不返回全文；配置与迁移备份位于本机 `%APPDATA%\IPhoneOtpSkill`，不属于分发包。

## 管理和恢复

在安装目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage.ps1 -Action Status
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage.ps1 -Action Start
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage.ps1 -Action Stop
# 恢复迁移前的 OtpBridge 配置、自启动与程序：
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\manage.ps1 -Action Rollback
```

删除前先停止后台程序，取消注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 下本项目的 `IPhoneOtpSkill` 自启动值；按需要删除本项目的 `IPhoneOtpSkill-LAN` 防火墙规则。接收程序重启会清空内存记录。

源码在 `scripts/`，测试在 `tests/`，协议、构建与故障排查在 [references](references/setup.md)。分享**原始发布包**即可，不要把 APPDATA 中的个人配置、Token 或迁移备份加入压缩包。

## 从源码构建

在 Windows x64 安装 Python 3.12 后，在仓库根目录执行：

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_release.py
```

构建脚本运行测试、打包两个 EXE、执行隔离验收，再生成 `dist/iphone-jiema-v版本号-windows-x64.zip` 和 SHA-256 文件。项目本身使用 Python 标准库，PyInstaller 仅用于构建。

GitHub Actions 会在推送与 PR 时测试并构建；推送与 `VERSION` 一致的 `v版本号` 标签后自动发布 Release。维护方式见 [发布说明](PUBLISHING.md)。本项目独立代码采用 MIT 许可，第三方来源与运行时许可见 [NOTICE](NOTICE.md)。
