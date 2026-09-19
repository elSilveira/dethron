"""What `dethron verify` says when there is nothing to say, and when a proof is broken.

The command's worth is entirely in what it refuses. A verifier that passes an empty
directory, or a custody packet whose signer was never recorded, would turn the whole
project's claim into a decoration.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from dethron.cli import build_parser, main
from dethron.wire import declared_expiry


def run(*args):
    """The command's own output is its result, so tests capture it instead of printing it."""
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = main(list(args))
    return code, json.loads(out.getvalue())


class EmptyTests(unittest.TestCase):
    def test_a_directory_with_no_identity_has_nothing_to_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, report = run('verify', tmp)
            self.assertEqual(code, 0)
            self.assertEqual(report['verdict'], 'nothing to verify')

    def test_the_parser_knows_every_command(self):
        parser = build_parser()
        for command in ('identity', 'relay', 'send', 'fetch', 'receipts', 'verify'):
            with self.subTest(command=command):
                self.assertTrue(hasattr(parser.parse_args([command, 'home', *(
                    ['--port', '1'] if command == 'relay' else
                    ['--to', 'x', '--relay', 'y', 'file'] if command == 'send' else
                    ['--source', 'x', '--relay', 'y'] if command == 'fetch' else
                    ['--relay', 'y'] if command == 'receipts' else [])]), 'run'))


class BrokenProofTests(unittest.TestCase):
    """A custody packet whose relay was never recorded cannot be checked, and must not pass."""

    def test_custody_without_its_relay_contact_fails_the_run(self):
        import RNS
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            RNS.Identity().to_file(str(home/'identity'))
            (home/'custody').mkdir()
            (home/'custody'/('c'*64+'.lxmf')).write_bytes(b'not even a packet')
            code, report = run('verify', str(home))
            self.assertEqual(code, 1)
            self.assertFalse(report['checks'][0]['passed'])

    def test_a_reconstructed_object_that_does_not_match_its_receipt_fails(self):
        import RNS
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            RNS.Identity().to_file(str(home/'identity'))
            (home/'output.bin').write_bytes(b'what actually landed')
            (home/'completion.json').write_text(json.dumps({'digest': 'e'*64}), encoding='utf-8')
            code, report = run('verify', str(home))
            self.assertEqual(code, 1)
            self.assertEqual(report['verdict'], 'fail')


class ExpiryTests(unittest.TestCase):
    def test_a_packet_declares_when_it_stops_being_valid(self):
        """Verification happens inside that window, so old proofs stay checkable."""
        from RNS.vendor import umsgpack
        envelope = json.dumps({'expires': 1789837482}).encode()
        raw = bytes(96)+umsgpack.packb([b'', b'dethron-g1', envelope, b''])
        self.assertEqual(declared_expiry(raw), 1789837482)


if __name__ == '__main__':
    unittest.main()
