import unittest

try:
    import LXMF
    import RNS
except ImportError as exc:
    raise unittest.SkipTest("requires .venv-gateway") from exc

from dethron.protocol import data_envelope, encode
from dethron.wire import authenticate


class WireTests(unittest.TestCase):
    def setUp(self):
        self.identity = RNS.Identity()
        self.source = RNS.Destination(self.identity, RNS.Destination.OUT, RNS.Destination.SINGLE,
                                      "lxmf", "delivery")
        self.dest = RNS.Destination(RNS.Identity(), RNS.Destination.OUT, RNS.Destination.SINGLE,
                                    "lxmf", "delivery")
        self.obj = data_envelope(self.source.hash.hex(), self.dest.hash.hex(), b"test", 100)

    def packed(self, obj):
        msg = LXMF.LXMessage(self.dest, self.source, encode(obj), "dethron-g1")
        msg.pack()
        return msg.packed

    def test_native_signed_message_is_verified(self):
        self.assertEqual(authenticate(self.packed(self.obj), self.identity.get_public_key(),
                                      self.dest.hash.hex(), 10), self.obj)

    def test_signature_content_key_and_destination_rejected(self):
        original = self.packed(self.obj)
        for offset in (0, 32, len(original)-2):
            changed = bytearray(original)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                authenticate(bytes(changed), self.identity.get_public_key(), self.dest.hash.hex(), 10)
        with self.assertRaises(ValueError):
            authenticate(original, RNS.Identity().get_public_key(), self.dest.hash.hex(), 10)

    def test_signed_envelope_cannot_impersonate_another_endpoint(self):
        for key in ("source", "destination"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                authenticate(self.packed({**self.obj, key: "0"*32}),
                             self.identity.get_public_key(), self.dest.hash.hex(), 10)


if __name__ == "__main__":
    unittest.main()
