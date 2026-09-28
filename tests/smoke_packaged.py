"""Exercise the packaged EXEs using temporary ports and synthetic data only."""
import argparse
import http.client
import json
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time


def free_ports():
    first = socket.socket()
    second = socket.socket()
    try:
        first.bind(("127.0.0.1", 0))
        second.bind(("127.0.0.1", 0))
        return first.getsockname()[1], second.getsockname()[1]
    finally:
        first.close()
        second.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    binary = args.bin.resolve()
    with tempfile.TemporaryDirectory(prefix="iphone-otp-smoke-", dir=args.work_dir) as temporary:
        ingest_port, reader_port = free_ports()
        settings = {"port": ingest_port, "readerPort": reader_port,
                    "phoneToken": secrets.token_urlsafe(32), "readerToken": secrets.token_urlsafe(32)}
        config = Path(temporary) / "config.json"
        config.write_text(json.dumps(settings), encoding="utf-8")
        def command(*arguments):
            result = subprocess.run([str(binary / "PhoneOtp.exe"), "--config", str(config), *arguments],
                                    capture_output=True, text=True, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            return json.loads(result.stdout)
        process = subprocess.Popen([str(binary / "PhoneOtpReceiver.exe"), "--config", str(config)],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(20):
                if command("status").get("ok"):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Packaged receiver did not become ready")
            ticket = command("arm", "--contains", "SMOKE-TEST", "--length", "6")
            assert ticket["ok"]
            pending = command("wait", "--ticket", ticket["ticket"], "--timeout", "0")
            assert pending["error"] == "timeout"
            conn = http.client.HTTPConnection("127.0.0.1", ingest_port, timeout=5)
            body = json.dumps({"message": "【SMOKE-TEST】验证码001234"}, ensure_ascii=False).encode()
            conn.request("POST", "/api/sms", iter([body[:8], body[8:]]),
                         {"Content-Type": "application/json", "Authorization": "Bearer " + settings["phoneToken"]},
                         encode_chunked=True)
            response = conn.getresponse()
            accepted = json.loads(response.read())
            conn.close()
            assert response.status == 200 and accepted["ok"]
            received = command("wait", "--ticket", ticket["ticket"], "--timeout", "2")
            assert received["code"] == "001234" and "message" not in received
            assert command("read", "--contains", "SMOKE-TEST")["error"] == "pending"
            print("Packaged receiver + CLI smoke test passed; synthetic data only.")
        finally:
            # Stop only the process tree this test created (PyInstaller uses a child).
            subprocess.run(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
