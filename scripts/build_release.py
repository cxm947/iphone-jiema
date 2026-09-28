"""Build a Windows x64 release from source; never reads user configuration."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ["SKILL.md", "README.md", "手机端极简教程.md", "Install.cmd", "Setup.cmd",
         "LICENSE", "NOTICE.md", "CHANGELOG.md", "VERSION", "requirements-build.txt", "PUBLISHING.md",
         ".gitignore", ".gitattributes"]
DIRECTORIES = ["agents", "references", "scripts", "tests", "licenses"]


def run(args, log=None):
    if log:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError("Build command failed; inspect " + str(log))
    else:
        subprocess.run(args, cwd=ROOT, check=True)


def copy_runtime_licenses(destination):
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Python runtime LICENSE.txt was not found")
    shutil.copy2(python_license, destination / "Python-LICENSE.txt")
    distribution = metadata.distribution("pyinstaller")
    copying = next((p for p in distribution.files or [] if str(p).replace("\\", "/").endswith("licenses/COPYING.txt")), None)
    if copying is None:
        raise RuntimeError("PyInstaller COPYING.txt was not found")
    shutil.copy2(distribution.locate_file(copying), destination / "PyInstaller-COPYING.txt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if os.name != "nt" or platform.machine().upper() not in ("AMD64", "X86_64"):
        raise SystemExit("Run this build on Windows x64.")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise SystemExit("VERSION must contain a stable major.minor.patch version.")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "tests" / "check_powershell.ps1")])
    work = (args.work_dir or ROOT / ".build").resolve()
    work.mkdir(parents=True, exist_ok=True)
    output = (args.output_dir or ROOT / "dist").resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-", dir=work) as temporary:
        scratch = Path(temporary)
        assert scratch.resolve().parent == work
        stage = scratch / "iphone-otp"
        stage.mkdir()
        for filename in FILES:
            shutil.copy2(ROOT / filename, stage / filename)
        for directory in DIRECTORIES:
            shutil.copytree(ROOT / directory, stage / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copy_runtime_licenses(stage / "licenses")
        for name, source, console in [("PhoneOtpReceiver", "receiver.py", "--noconsole"),
                                      ("PhoneOtp", "otp.py", "--console")]:
            log = work / (name + ".log")
            run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", console,
                 "--name", name, "--distpath", str(stage / "bin"),
                 "--workpath", str(scratch / "pyinstaller" / name), "--specpath", str(scratch),
                 str(ROOT / "scripts" / source)], log=log)
            print("Built " + name, flush=True)
        run([sys.executable, str(ROOT / "tests" / "smoke_packaged.py"), "--bin", str(stage / "bin"), "--work-dir", str(scratch)])
        hashes = {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(stage.rglob("*")) if p.is_file()}
        manifest = {"version": version, "platform": "Windows x64", "python": platform.python_version(),
                    "pyinstaller": metadata.version("pyinstaller"), "files": hashes}
        (stage / "SHA256SUMS.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        package = output / ("iphone-jiema-v" + version + "-windows-x64.zip")
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, "iphone-otp/" + path.relative_to(stage).as_posix())
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Release archive failed integrity check")
        digest = hashlib.sha256(package.read_bytes()).hexdigest()
        package.with_suffix(".zip.sha256").write_text(digest + "  " + package.name + "\n", encoding="ascii")
        print(json.dumps({"ok": True, "archive": str(package), "sha256": digest}))


if __name__ == "__main__":
    main()
