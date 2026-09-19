"""Proof of entry: a relay attests, by transient id, that it holds a message.

A custody attestation is a claim by the relay. It proves the message was
confided to the network; it never proves delivery. Only the recipient's
receipt does that.
"""
import hashlib
import time
import uuid

from RNS.vendor import umsgpack

from .protocol import decode, encode
from .wire import authenticate

LIFETIME = 3600


def request(origin, relay, transient_id, public_key, expires=None, request_id=None):
    obj = {"version": 1, "kind": "custody_request", "id": request_id or uuid.uuid4().hex,
           "source": origin, "destination": relay, "expires": expires or int(time.time())+LIFETIME,
           "transient_id": transient_id, "public_key": public_key}
    return decode(encode(obj), 0)


def attest(req, relay, recipient, stored, received):
    """Built by the relay from the bytes it actually holds on disk."""
    obj = {"version": 1, "kind": "custody", "id": req["id"], "source": relay,
           "destination": req["source"], "expires": req["expires"],
           "transient_id": req["transient_id"], "recipient": recipient,
           "stored_size": len(stored), "stored_digest": hashlib.sha256(stored).hexdigest(),
           "received": int(received)}
    return decode(encode(obj), 0)


def refuse(req, relay, reason):
    """Absence of custody must be explicit, never silence."""
    obj = {"version": 1, "kind": "custody_refusal", "id": req["id"], "source": relay,
           "destination": req["source"], "expires": req["expires"],
           "transient_id": req["transient_id"], "reason": reason}
    return decode(encode(obj), 0)


def peek(raw, now):
    """Untrusted look at the envelope inside a packed LXMF message, only to pick a key."""
    if not isinstance(raw, bytes) or len(raw) < 97:
        raise ValueError("short packet")
    return decode(umsgpack.unpackb(raw[96:])[2], now)


def accept_request(raw, relay, now, known=None):
    """The requester's key comes from the announce cache or from the request itself;
    either way the LXMF signature must bind that key to the packet's source hash."""
    try:
        key = known if known is not None else bytes.fromhex(peek(raw, now)["public_key"])
    except Exception as exc:
        raise ValueError(f"unreadable custody request: {exc}") from exc
    obj = authenticate(raw, key, relay, now)
    if obj["kind"] != "custody_request" or obj["public_key"] != key.hex():
        raise ValueError("not a custody request signed by its declared key")
    return obj, key


def verify(raw, relay_public_key, origin, transient_id, now):
    """Only a signed custody envelope for exactly this transient id counts as proof of entry."""
    obj = authenticate(raw, relay_public_key, origin, now)
    if obj["kind"] != "custody":
        raise ValueError(f"not a custody attestation: {obj['kind']}")
    if obj["transient_id"] != transient_id:
        raise ValueError("custody attests a different message")
    return obj


def verify_refusal(raw, relay_public_key, origin, transient_id, now):
    obj = authenticate(raw, relay_public_key, origin, now)
    if obj["kind"] != "custody_refusal" or obj["transient_id"] != transient_id:
        raise ValueError("not a refusal for this message")
    return obj
