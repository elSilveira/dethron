import json
import unittest

from dethron.protocol import data_envelope, decode, encode, receipt_envelope


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.message = data_envelope("a"*32, "b"*32, b"hello", 100, message_id="c"*32)

    def test_round_trip_and_receipt_binding(self):
        self.assertEqual(decode(encode(self.message), 10), self.message)
        receipt = receipt_envelope(self.message)
        self.assertEqual(receipt["source"], self.message["destination"])
        self.assertEqual(receipt["digest"], self.message["digest"])
        self.assertNotIn("payload", receipt)

    def test_corruption_version_size_and_expiry_rejected(self):
        for change in ({"version": 2}, {"size": 6}, {"digest": "0"*64},
                       {"payload": "%%%"}, {"expires": True}, {"id": "../escape"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decode(json.dumps({**self.message, **change}).encode(), 10)
        with self.assertRaises(ValueError):
            decode(encode(self.message), 100)

    def test_unknown_and_duplicate_fields_rejected(self):
        with self.assertRaises(ValueError):
            decode(json.dumps({**self.message, "magic": 1}).encode(), 10)
        with self.assertRaises(ValueError):
            decode(encode(self.message)[:-1] + b',"version":1}', 10)

    def test_oversized_payload_rejected_before_queue(self):
        with self.assertRaises(ValueError):
            data_envelope("a"*32, "b"*32, b"x"*(1048576+1), 100)


if __name__ == "__main__":
    unittest.main()
