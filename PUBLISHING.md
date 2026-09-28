# GitHub 维护与发布

项目仓库：[cxm947/iphone-jiema](https://github.com/cxm947/iphone-jiema)。技能标识保持 `iphone-otp`，已有用户无需改变调用名称。

## 仓库与安装包

- Git 仓库保存源码、技能说明、教程、测试、许可证与自动化工作流。
- `bin/`、`.build/`、`dist/`、配置与迁移备份不进入 Git 历史。
- Windows 用户从 Releases 下载完整 `iphone-jiema-v版本号-windows-x64.zip`，里面有自包含 EXE。
- 源码包无法直接安装，需要先在 Windows x64 上执行构建脚本。

## 发布新版本

1. 更新 `VERSION` 与 `CHANGELOG.md`，保留 OtpBridge 的署名、链接和来源说明。
2. 提交到 main；GitHub Actions 自动跑测试、构建 EXE、用模拟短信检查打包后的程序。也可手动运行 Actions 中的 Windows build and test。
3. 确认构建通过后，推送匹配版本的 Git 标签。例如 VERSION 为 1.0.1 时：

```powershell
git tag v1.0.1
git push origin v1.0.1
```

标签构建成功后，工作流用仓库自带的 `GITHUB_TOKEN` 创建 Release，上传 ZIP 与 `.sha256` 文件。无需保存个人 PAT。标签与 VERSION 不一致会停止发布。

本地构建：

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_release.py
```

生成文件在 `dist/`。仓库管理员可在 GitHub Releases 网页手动上传这些文件。GitHub 自动生成的 Source code ZIP 不是 Windows 安装包。

## 可复现范围

构建工具主版本固定在 `requirements-build.txt`，工作流使用 Python 3.12；每个发布包内部的 `SHA256SUMS.json` 记录实际运行时版本与文件校验和。不同运行时补丁、构建时间或系统会让 EXE 的哈希不同，因此不声称逐字节可重复。

测试使用临时 Token、临时端口和模拟短信，不读取个人短信或 APPDATA 配置。首次在新网络安装后，应再用实体 iPhone 收到一条含“验证码”的短信确认自动推送。

实现参考：[GitHub Python 构建文档](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)、[在工作流中使用 GitHub CLI](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-github-cli)。
