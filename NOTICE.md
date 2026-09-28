# 来源与署名

## 感谢 OtpBridge

- 原项目：[OtpBridge / OBW](https://github.com/csyxcsyx/OBW)
- 原作者：[csyxcsyx](https://github.com/csyxcsyx)
- 本项目使用的思路来源：iPhone 快捷指令收到短信后，通过局域网 HTTP POST 推送给 Windows 接收端。
- 兼容点：`POST /api/sms`、Bearer Authorization、JSON `message`/可选 `sender`、`GET /health`。
- 本机已验证兼容的上游发布包：v1.4。

本项目不是 OtpBridge 官方版本，也不暗示作者参与或认可。本分发包不包含 OtpBridge 的源码、二进制、图标或截图；接收端、读码接口、安装脚本与技能由本项目独立实现。查阅上游仓库时未发现明确的许可证文件，因此不将其代码作为本项目可自由再分发的组成部分。

如未来改为基于 OtpBridge 源码派生发布，应先核实上游许可证或取得许可，并保留作者、原许可、来源和修改说明。

## 打包运行时

Windows EXE 使用 Python 与 PyInstaller 打包。运行时相关许可随本包的 `licenses/` 保留；它们不改变 OtpBridge 的权利归属。源码构建说明见 `references/protocol.md`。
