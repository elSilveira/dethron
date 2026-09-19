"""Bounded application envelopes. Authentication is provided by the LXMF envelope."""
import base64
import hashlib
import json
import re
import uuid

MAX_PAYLOAD = 1048576
# The tag every packet carries so a foreign LXMF message cannot pass as one of ours. It
# is a wire constant, not a product name: changing it would stop this code verifying the
# evidence already published, which is the whole point of keeping the evidence.
APPLICATION = b"dethron-g1"
MAX_WIRE = 1500000
MAX_REASON = 200
BASE = {"version", "kind", "id", "source", "destination", "expires"}
COMMON = BASE | {"size", "digest"}
# Custody envelopes (V1) are proof of entry only: a relay attests, by transient id, what it holds.
FIELDS = {
    "data": COMMON | {"payload"},
    "receipt": COMMON,
    "custody_request": BASE | {"transient_id", "public_key"},
    "custody": BASE | {"transient_id", "recipient", "stored_size", "stored_digest", "received"},
    "custody_refusal": BASE | {"transient_id", "reason"},
}
HEX = {"id": 32, "source": 32, "destination": 32, "recipient": 32, "digest": 64,
       "transient_id": 64, "stored_digest": 64, "public_key": 128}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _hex(obj, key):
    value = obj[key]
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{HEX[key]}}}", value):
        raise ValueError(f"invalid {key}")


def decode(raw, now):
    if not isinstance(raw, bytes) or len(raw) > MAX_WIRE:
        raise ValueError("invalid envelope size")
    try:
        obj = json.loads(raw, object_pairs_hook=_unique)
        if not isinstance(obj, dict) or type(obj.get("version")) is not int or obj["version"] != 1:
            raise ValueError("unsupported envelope version")
        kind = obj.get("kind")
        if kind not in FIELDS:
            raise ValueError("unknown kind")
        if set(obj) != FIELDS[kind]:
            raise ValueError("unexpected fields")
        for key in sorted(FIELDS[kind] & set(HEX)):
            _hex(obj, key)
        if type(obj["expires"]) is not int or not now < obj["expires"] <= 253402300799:
            raise ValueError("expired or invalid expiry")
        if kind in ("data", "receipt"):
            if type(obj["size"]) is not int or not 0 < obj["size"] <= MAX_PAYLOAD:
                raise ValueError("invalid payload size")
        if kind == "data":
            content = base64.b64decode(obj["payload"], validate=True)
            if len(content) != obj["size"] or hashlib.sha256(content).hexdigest() != obj["digest"]:
                raise ValueError("content does not match manifest")
        if kind == "custody":
            if type(obj["stored_size"]) is not int or not 0 < obj["stored_size"] <= MAX_WIRE:
                raise ValueError("invalid stored size")
            if type(obj["received"]) is not int or not 0 < obj["received"] <= obj["expires"]:
                raise ValueError("invalid custody time")
        if kind == "custody_refusal":
            reason = obj["reason"]
            if not isinstance(reason, str) or not 0 < len(reason) <= MAX_REASON or not reason.isprintable():
                raise ValueError("invalid refusal reason")
        return obj
    except (TypeError, KeyError, UnicodeError) as exc:
        raise ValueError("invalid envelope") from exc


def data_envelope(source, destination, content, expires, message_id=None):
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_PAYLOAD:
        raise ValueError("invalid payload size")
    obj = {"version": 1, "kind": "data", "id": message_id or uuid.uuid4().hex,
           "source": source, "destination": destination, "expires": expires,
           "size": len(content), "digest": hashlib.sha256(content).hexdigest(),
           "payload": base64.b64encode(content).decode("ascii")}
    return decode(encode(obj), 0)


def receipt_envelope(message):
    return {**{key: value for key, value in message.items() if key != "payload"},
            "kind": "receipt", "source": message["destination"], "destination": message["source"]}
