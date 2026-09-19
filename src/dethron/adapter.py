"""LXMF direct delivery adapter. pump() is explicit; no simulated network fallback."""
import threading
import time

import LXMF
import RNS

from .protocol import APPLICATION, encode
from .wire import authenticate


class Adapter:
    def __init__(self, router, source, mailbox, emit):
        self.router, self.source, self.mailbox, self.emit = router, source, mailbox, emit
        self.active = set()
        self.lock = threading.RLock()
        router.register_delivery_callback(self.receive)

    def receive(self, message):
        try:
            identity = RNS.Identity.recall(message.source_hash)
            if identity is None:
                raise ValueError("unknown source identity")
            obj = authenticate(message.packed, identity.get_public_key(), self.source.hash.hex(), time.time())
            fresh = self.mailbox.accept_verified(obj, message.packed, time.time())
            self.emit("confirmed" if obj["kind"] == "receipt" else "received",
                      id=obj["id"], fresh=fresh, digest=obj["digest"])
        except Exception as exc:
            self.emit("rejected", error=repr(exc))

    def transmit(self, destination, body, callback=None, failed=None):
        dest_hash = bytes.fromhex(destination)
        identity = RNS.Identity.recall(dest_hash)
        if identity is None:
            RNS.Transport.request_path(dest_hash)
            return False
        target = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
        message = LXMF.LXMessage(target, self.source, body, APPLICATION, desired_method=LXMF.LXMessage.DIRECT)
        if callback:
            message.register_delivery_callback(callback)
        if failed:
            message.register_failed_callback(failed)
        self.router.handle_outbound(message)
        return True

    def _complete(self, key, message_id, succeeded):
        with self.lock:
            if succeeded:
                self.mailbox.handoff(key)
            self.active.discard(key)
        self.emit("handoff" if succeeded else "attempt_failed", id=message_id)

    def pump(self):
        with self.lock:
            for item in self.mailbox.pending(time.time()):
                key, obj = item["key"], item["envelope"]
                if key in self.active:
                    continue
                dest_hash = bytes.fromhex(obj["destination"])
                # Native LXMF can reuse a backchannel even without a cached route.
                if RNS.Identity.recall(dest_hash) is None:
                    RNS.Transport.request_path(dest_hash)
                    self.emit("no_path", id=obj["id"])
                    continue
                self.mailbox.begin_attempt(key, time.time())
                self.active.add(key)
                success = lambda m, k=key, i=obj["id"]: self._complete(k, i, True)
                failure = lambda m, k=key, i=obj["id"]: self._complete(k, i, False)
                try:
                    sent = self.transmit(obj["destination"], encode(obj), success, failure)
                    if not sent:
                        self.active.discard(key)
                except Exception:
                    self.active.discard(key)
                    raise
