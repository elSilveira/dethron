import itertools
import tempfile
import unittest
from pathlib import Path

from dethron.assembly import Assembly
from dethron.protocol import data_envelope, encode
from dethron.erasure import parity_split, reconstruct
from dethron.parts import validate


class ErasureTests(unittest.TestCase):
    def test_every_pair_recovers_odd_and_even_lengths(self):
        for content in (b'abcde', bytes(range(256))*192):
            parts = parity_split(content, 'f'*32)
            for pair in itertools.combinations(parts, 2):
                parsed = [validate(encode(p)) for p in pair]
                self.assertEqual(reconstruct(parsed[0][0], {i: b for _, i, b in parsed}), content)

    def test_single_shard_is_incomplete(self):
        m, i, b = validate(encode(parity_split(b'abcde', 'f'*32)[2]))
        self.assertIsNone(reconstruct(m, {i: b}))

    def test_restart_duplicate_and_parity_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'assembly.db'
            parts = parity_split(b'abcde', 'f'*32)
            store = Assembly(path, 'b'*32)
            def add(index):
                obj = data_envelope('a'*32, 'b'*32, encode(parts[index]), 100)
                return store.accept_verified(obj, b'signed', 10)
            self.assertFalse(add(2)['complete'])
            self.assertFalse(add(2)['fresh'])
            store = Assembly(path, 'b'*32)
            result = add(0)
            self.assertTrue(result['complete'])
            self.assertEqual(store.content(result['key']), b'abcde')

    def test_false_whole_digest_rolls_back_last_part(self):
        with tempfile.TemporaryDirectory() as temp:
            parts = parity_split(b'abcdef', 'f'*32)
            for part in parts:
                part['manifest']['digest'] = '0'*64
            store = Assembly(Path(temp)/'assembly.db', 'b'*32)
            def add(index):
                return store.accept_verified(data_envelope('a'*32, 'b'*32, encode(parts[index]), 100), b'x', 10)
            add(0)
            with self.assertRaises(ValueError):
                add(2)
            self.assertEqual(store.snapshot()[0]['count'], 1)


if __name__ == '__main__':
    unittest.main()
