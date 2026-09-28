"""Read phone-pushed OTPs via the local receiver API; no clipboard access."""
import argparse
import http.client
import json
import sys
import time
from otp_core import load_config


def request(config, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", config["readerPort"], timeout=5)
    try:
        headers = {"Authorization": "Bearer " + config["readerToken"]}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        conn.request("GET" if body is None else "POST", path, data, headers)
        response = conn.getresponse()
        result = json.loads(response.read(8192))
        if not isinstance(result, dict):
            return {"ok": False, "error": "invalid_receiver_response"}
        return result
    except (OSError, ValueError, http.client.HTTPException):
        return {"ok": False, "error": "receiver_unavailable"}
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Alternative local config file; never put tokens in arguments")
    modes = parser.add_subparsers(dest="mode", required=True)
    modes.add_parser("status")
    arm = modes.add_parser("arm", help="Create ticket before requesting a new SMS")
    read = modes.add_parser("read", help="Consume an already-received, unconsumed code")
    for mode in (arm, read):
        mode.add_argument("--contains", default="", help="Literal service keyword in SMS body")
        mode.add_argument("--sender", default="", help="Exact sender if the phone supplies it")
        mode.add_argument("--length", type=int, choices=range(4, 9))
    read.add_argument("--max-age", type=int, choices=range(1, 301), default=120, metavar="1..300")
    wait = modes.add_parser("wait")
    wait.add_argument("--ticket", required=True)
    wait.add_argument("--timeout", type=int, choices=range(0, 31), default=30, metavar="0..30")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValueError, AttributeError):
        result = {"ok": False, "error": "config_missing_or_invalid"}
    else:
        if args.mode == "status":
            result = request(config, "/api/status")
        elif args.mode in ("arm", "read"):
            body = {"contains": args.contains, "sender": args.sender, "length": args.length}
            if args.mode == "read":
                body["maxAge"] = args.max_age
            result = request(config, "/api/" + args.mode, body)
        else:
            deadline = time.monotonic() + args.timeout
            while True:
                result = request(config, "/api/take", {"ticket": args.ticket})
                if result.get("error") != "pending":
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    result = {"ok": False, "error": "timeout", "retryable": True}
                    break
                time.sleep(min(0.5, remaining))
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
