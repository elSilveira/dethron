"""Receiver boundary: authenticate first, then persist exact parts or a whole object."""
import base64
import hashlib

import LXMF
import RNS

from .assembly import Assembly
from .protocol import APPLICATION, encode, receipt_envelope
from .wire import authenticate
import time


class Receiver:
    def __init__(self, home, source, mode, emit):
        self.home, self.source, self.mode, self.emit = home, source, mode, emit
        self.assembly = Assembly(home / "assembly.db", source.hash.hex()) if mode != "whole" else None

    def receive(self, message):
        try:
            peer = RNS.Identity.recall(message.source_hash)
            if peer is None:
                raise ValueError("unknown origin")
            obj = authenticate(message.packed, peer.get_public_key(), self.source.hash.hex(), time.time())
            if obj["kind"] != "data":
                raise ValueError("expected data")
            if self.assembly:
                result = self.assembly.accept_verified(obj, message.packed, time.time())
                content = self.assembly.content(result["key"])
                obligation = {**obj, "id": result["id"], "digest": result["digest"], "size": result["size"]}
            else:
                content = base64.b64decode(obj["payload"], validate=True)
                result = {"id": obj["id"], "complete": True, "fresh": not (self.home/"output.bin").exists(), "count": 1}
                obligation = obj
            folder = self.home / "packets"
            folder.mkdir(exist_ok=True)
            packet = folder / (message.hash.hex()+".lxmf")
            if not packet.exists():
                packet.write_bytes(message.packed)
            if content is not None:
                (self.home / "output.bin").write_bytes(content)
                target = RNS.Destination(peer, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
                receipt = LXMF.LXMessage(target, self.source, encode(receipt_envelope(obligation)), APPLICATION)
                receipt.pack()
                (self.home / "completion.lxmf").write_bytes(receipt.packed)
                # The envelope itself, so the node can carry it back through relays (V1).
                (self.home / "completion.json").write_bytes(encode(receipt_envelope(obligation)))
            self.emit("accepted", **result)
        except Exception as exc:
            self.emit("rejected", error=repr(exc))

    def status(self):
        output = self.home / "output.bin"
        return {"completed": output.exists(), "sha256": hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None,
                "objects": self.assembly.snapshot() if self.assembly else []}
