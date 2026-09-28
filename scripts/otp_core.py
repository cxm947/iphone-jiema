"""Phone-push OTP inbox. Standard library only; never uses the clipboard."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from datetime import datetime, timezone

APP = "IPhoneOtpSkill"
TTL = 300
WAIT_TTL = 180
MAX_BODY = 32768


def config_path():
    return Path(os.environ.get("APPDATA", str(Path.home()))) / APP / "config.json"


def load_config(path=None):
    config = json.loads(Path(path or config_path()).read_text(encoding="utf-8-sig"))
    for key in ("port", "readerPort"):
        if type(config.get(key)) is not int or not 1 <= config[key] <= 65535:
            raise ValueError("invalid_port")
    if config["port"] == config["readerPort"]:
        raise ValueError("ports_must_differ")
    for key in ("phoneToken", "readerToken"):
        if not isinstance(config.get(key), str) or len(config[key]) < 16:
            raise ValueError("invalid_token")
    return config


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def authorized(header, token):
    if not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[7:].strip().encode(), token.encode())


def extract_code(message):
    lead = r"(?:验证码|校验码|动态码|短信码|verification\s+code|security\s+code|otp|code)"
    pattern = lead + r"\s*(?:(?:为|是|is|:|：|=|-)\s*)*[【\[(（]?\s*([A-Za-z0-9]{4,8})(?![A-Za-z0-9])"
    codes = set(re.findall(pattern, message, re.IGNORECASE))
    if not codes:
        codes = {s for s in re.findall(r"(?<![A-Za-z0-9])([A-Za-z0-9]{4,8})(?![A-Za-z0-9])", message)
                 if re.search(r"[0-9]", s)}
    if not codes:
        raise ValueError("code_not_found")
    if len(codes) > 1:
        raise ValueError("ambiguous_code_in_message")
    return next(iter(codes))


def filters(body):
    result = {}
    for key in ("contains", "sender"):
        value = body.get(key, "")
        if not isinstance(value, str) or len(value) > 120:
            raise ValueError("invalid_filter")
        result[key] = value.strip()
    length = body.get("length")
    if length is not None and (type(length) is not int or not 4 <= length <= 8):
        raise ValueError("invalid_length")
    result["length"] = length
    return result


class Inbox:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.records = []
        self.tickets = {}
        self.sequence = 0
        self.session = secrets.token_hex(16)

    def purge(self):
        with self.lock:
            now = self.clock()
            self.records = [r for r in self.records if now - r["time"] < TTL]
            self.tickets = {k: t for k, t in self.tickets.items() if now - t["time"] < WAIT_TTL}

    def ingest(self, body):
        message = body.get("message")
        sender = body.get("sender", "")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is required")
        if not isinstance(sender, str) or len(sender) > 120:
            raise ValueError("invalid_sender")
        code = extract_code(message)
        digest = hashlib.sha256((sender + "\0" + message).encode()).hexdigest()
        with self.lock:
            self.purge()
            now = self.clock()
            for record in reversed(self.records):
                if record["digest"] == digest and now - record["time"] < 10:
                    return {"ok": True, "code": code, "duplicate": True}
            self.sequence += 1
            hint = re.search(r"【([^】]{1,60})】", message)
            self.records.append({"id": self.sequence, "time": now, "message": message,
                                 "sender": sender, "code": code, "digest": digest,
                                 "serviceHint": hint[1] if hint else "", "consumed": False})
            self.records = self.records[-50:]
            return {"ok": True, "code": code, "duplicate": False}

    def status(self):
        with self.lock:
            self.purge()
            return {"ok": True, "app": APP, "session": self.session,
                    "pendingCount": sum(not r["consumed"] for r in self.records),
                    "retentionSeconds": TTL, "clipboardUsed": False}

    def arm(self, body):
        selection = filters(body)
        with self.lock:
            self.purge()
            if len(self.tickets) >= 32:
                raise ValueError("too_many_active_tickets")
            ticket = secrets.token_urlsafe(24)
            now = self.clock()
            self.tickets[ticket] = {"after": self.sequence, "time": now, "filters": selection, "delivered": None}
            return {"ok": True, "ticket": ticket, "armedAtUtc": utc(now),
                    "expiresAtUtc": utc(now + WAIT_TTL), "filters": selection}

    @staticmethod
    def matches(record, selection):
        return (not selection["contains"] or selection["contains"].casefold() in record["message"].casefold()) and \
               (not selection["sender"] or selection["sender"] == record["sender"]) and \
               (not selection["length"] or len(record["code"]) == selection["length"])

    def deliver(self, records, ticket=None):
        if not records:
            return {"ok": False, "error": "pending"}
        if len(records) > 1:
            return {"ok": False, "error": "ambiguous", "candidateCount": len(records)}
        record = records[0]
        replayed = record["consumed"]
        record["consumed"] = True
        if ticket is not None:
            ticket["delivered"] = record["id"]
        now = self.clock()
        return {"ok": True, "id": record["id"], "code": record["code"],
                "sender": record["sender"], "serviceHint": record["serviceHint"],
                "receivedAtUtc": utc(record["time"]), "ageSeconds": round(now - record["time"], 1),
                "source": "authenticated_phone_push", "consumed": True, "replayed": replayed}

    def take(self, body):
        token = body.get("ticket")
        if not isinstance(token, str):
            raise ValueError("ticket_required")
        with self.lock:
            self.purge()
            ticket = self.tickets.get(token)
            if ticket is None:
                return {"ok": False, "error": "ticket_expired_or_unknown"}
            if ticket["delivered"] is not None:
                return self.deliver([r for r in self.records if r["id"] == ticket["delivered"]])
            records = [r for r in self.records if not r["consumed"] and r["id"] > ticket["after"]
                       and self.matches(r, ticket["filters"])]
            return self.deliver(records, ticket)

    def read(self, body):
        selection = filters(body)
        max_age = body.get("maxAge", 120)
        if type(max_age) is not int or not 1 <= max_age <= TTL:
            raise ValueError("invalid_max_age")
        with self.lock:
            self.purge()
            records = [r for r in self.records if not r["consumed"] and self.clock() - r["time"] <= max_age
                       and self.matches(r, selection)]
            return self.deliver(records)
