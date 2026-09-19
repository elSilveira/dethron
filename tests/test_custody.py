import hashlib
import json
import unittest

try:
    import LXMF
    import RNS
except ImportError as exc:
    raise unittest.SkipTest("requires .venv-gateway") from exc

from dethron.custody import accept_request, attest, refuse, request, verify, verify_refusal
from dethron.protocol import data_envelope, decode, encode


def endpoint(identity):
    return RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")


def packed(obj, source, destination):
    message = LXMF.LXMessage(destination, source, encode(obj), "dethron-g1")
    message.pack()
    return message.packed


class CustodyEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.origin_identity, self.relay_identity = RNS.Identity(), RNS.Identity()
        self.origin, self.relay = endpoint(self.origin_identity), endpoint(self.relay_identity)
        self.tid = hashlib.sha256(b"stored message").hexdigest()
        self.req = request(self.origin.hash.hex(), self.relay.hash.hex(), self.tid,
                           self.origin_identity.get_public_key().hex(), expires=100)
        self.stored = b"stored message bytes plus stamp"

    def test_request_attestation_and_refusal_round_trip(self):
        custody = attest(self.req, self.relay.hash.hex(), "d"*32, self.stored, 50)
        refusal = refuse(self.req, self.relay.hash.hex(), "transient id not in store")
        for obj in (self.req, custody, refusal):
            with self.subTest(kind=obj["kind"]):
                self.assertEqual(decode(encode(obj), 10), obj)
        self.assertEqual(custody["stored_digest"], hashlib.sha256(self.stored).hexdigest())
        self.assertEqual(custody["destination"], self.req["source"])
        self.assertEqual(custody["id"], self.req["id"])

    def test_custody_fields_are_bounded(self):
        custody = attest(self.req, self.relay.hash.hex(), "d"*32, self.stored, 50)
        for change in ({"stored_size": 0}, {"stored_size": -1}, {"transient_id": "ab"},
                       {"received": 101}, {"received": 0}, {"recipient": "x"*32}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decode(json.dumps({**custody, **change}).encode(), 10)
        refusal = refuse(self.req, self.relay.hash.hex(), "ok")
        for reason in ("", "x"*201, "line\nbreak"):
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                decode(json.dumps({**refusal, "reason": reason}).encode(), 10)
        with self.assertRaises(ValueError):
            decode(json.dumps({**self.req, "public_key": "0"*127}).encode(), 10)


class CustodySignatureTests(unittest.TestCase):
    def setUp(self):
        self.origin_identity, self.relay_identity = RNS.Identity(), RNS.Identity()
        self.origin, self.relay = endpoint(self.origin_identity), endpoint(self.relay_identity)
        self.tid = hashlib.sha256(b"stored message").hexdigest()
        self.req = request(self.origin.hash.hex(), self.relay.hash.hex(), self.tid,
                           self.origin_identity.get_public_key().hex(), expires=100)
        self.stored = b"stored message bytes plus stamp"

    def test_relay_accepts_only_a_request_signed_by_its_declared_key(self):
        raw = packed(self.req, self.origin, self.relay)
        obj, key = accept_request(raw, self.relay.hash.hex(), 10)
        self.assertEqual(obj, self.req)
        self.assertEqual(key, self.origin_identity.get_public_key())
        impostor = RNS.Identity()
        with self.assertRaises(ValueError):
            accept_request(packed(self.req, endpoint(impostor), self.relay), self.relay.hash.hex(), 10)
        lying = {**self.req, "public_key": impostor.get_public_key().hex()}
        with self.assertRaises(ValueError):
            accept_request(packed(lying, self.origin, self.relay), self.relay.hash.hex(), 10)

    def test_signed_custody_is_proof_of_entry_for_exactly_one_message(self):
        custody = attest(self.req, self.relay.hash.hex(), "d"*32, self.stored, 50)
        raw = packed(custody, self.relay, self.origin)
        self.assertEqual(verify(raw, self.relay_identity.get_public_key(), self.origin.hash.hex(),
                                self.tid, 10), custody)
        other = hashlib.sha256(b"another message").hexdigest()
        with self.assertRaises(ValueError):
            verify(raw, self.relay_identity.get_public_key(), self.origin.hash.hex(), other, 10)

    def test_refusal_and_data_are_never_custody(self):
        refusal = refuse(self.req, self.relay.hash.hex(), "transient id not in store")
        raw = packed(refusal, self.relay, self.origin)
        with self.assertRaises(ValueError):
            verify(raw, self.relay_identity.get_public_key(), self.origin.hash.hex(), self.tid, 10)
        self.assertEqual(verify_refusal(raw, self.relay_identity.get_public_key(),
                                        self.origin.hash.hex(), self.tid, 10), refusal)
        data = data_envelope(self.relay.hash.hex(), self.origin.hash.hex(), b"payload", 100)
        with self.assertRaises(ValueError):
            verify(packed(data, self.relay, self.origin), self.relay_identity.get_public_key(),
                   self.origin.hash.hex(), self.tid, 10)

    def test_custody_signed_by_an_impostor_is_rejected(self):
        custody = attest(self.req, self.relay.hash.hex(), "d"*32, self.stored, 50)
        impostor = RNS.Identity()
        raw = packed(custody, endpoint(impostor), self.origin)
        with self.assertRaises(ValueError):
            verify(raw, self.relay_identity.get_public_key(), self.origin.hash.hex(), self.tid, 10)
        with self.assertRaises(ValueError):
            verify(raw, impostor.get_public_key(), self.origin.hash.hex(), self.tid, 10)


if __name__ == "__main__":
    unittest.main()
