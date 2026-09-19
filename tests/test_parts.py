import base64
import copy
from pathlib import Path
import tempfile
import unittest

from dethron.parts import split, validate
from dethron.assembly import Assembly
from dethron.protocol import data_envelope, encode


class PartsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "assembly.db"
        self.content = bytes(range(256))*24
        self.parts = split(self.content, 3, "c"*32)
        self.store = Assembly(self.path, "b"*32)

    def add(self, part, store=None):
        envelope = data_envelope("a"*32, "b"*32, encode(part), 100)
        return (store or self.store).accept_verified(envelope, b"signed evidence", 10)

    def test_out_of_order_restart_and_exact_completion(self):
        self.assertFalse(self.add(self.parts[2])["complete"])
        reopened = Assembly(self.path, "b"*32)
        self.assertFalse(self.add(self.parts[0], reopened)["complete"])
        result = self.add(self.parts[1], reopened)
        self.assertTrue(result["complete"])
        self.assertEqual(reopened.content(result["key"]), self.content)

    def test_duplicates_cannot_replace_a_missing_part(self):
        self.add(self.parts[0])
        for _ in range(3):
            result = self.add(self.parts[0])
            self.assertFalse(result["fresh"])
        result = self.add(self.parts[2])
        self.assertEqual(result["count"], 2)
        self.assertFalse(result["complete"])
        self.assertIsNone(self.store.content(result["key"]))

    def test_corruption_then_valid_replica(self):
        bad = copy.deepcopy(self.parts[0])
        bad["data"] = base64.b64encode(b"x"*2048).decode()
        with self.assertRaises(ValueError):
            self.add(bad)
        self.assertEqual(self.store.snapshot(), [])
        for part in self.parts:
            result = self.add(part)
        self.assertTrue(result["complete"])

    def test_incompatible_manifest_does_not_mix(self):
        self.add(self.parts[0])
        other = split(b"z"*len(self.content), 3, "c"*32)
        with self.assertRaises(ValueError):
            self.add(other[1])
        self.assertEqual(self.store.snapshot()[0]["count"], 1)

    def test_bad_scheme_version_index_and_manifest_rejected(self):
        for field, value in (("version", 2), ("scheme", "magic"), ("size", 1)):
            obj = copy.deepcopy(self.parts[0])
            obj["manifest"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(encode(obj))
        obj = {**self.parts[0], "index": True}
        with self.assertRaises(ValueError):
            validate(encode(obj))

    def test_capacity_failure_keeps_no_partial_manifest(self):
        limited = Assembly(Path(self.temp.name)/"limited.db", "b"*32, max_bytes=10)
        with self.assertRaises(ValueError):
            self.add(self.parts[0], limited)
        self.assertEqual(limited.snapshot(), [])


if __name__ == "__main__":
    unittest.main()
