"""The whole claim, end to end, with real nodes on loopback.

Opt in, because it starts three Reticulum instances, binds a port and takes a couple of
minutes:

    DETHRON_ROUNDTRIP=1 python -m pytest tests/test_roundtrip.py

What it proves is the thing the project exists for, and it proves it the hard way: the
sender leaves before the recipient ever appears, and comes back later to a receipt it can
check without trusting the relay that carried it.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

PORT = int(os.environ.get('DETHRON_ROUNDTRIP_PORT', '45817'))
PAYLOAD = b'the quick brown fox jumps over the lazy dog\n'*240


def cli(home, *args, cwd, timeout=300):
    done = subprocess.run([sys.executable, '-m', 'dethron.cli', home, *map(str, args)],
                          capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
    if '{' not in done.stdout:
        raise AssertionError(f'{args}: no result\nstdout:{done.stdout}\nstderr:{done.stderr[-2000:]}')
    return json.loads(done.stdout[done.stdout.index('{'):done.stdout.rindex('}')+1])


@unittest.skipUnless(os.environ.get('DETHRON_ROUNDTRIP'), 'opt-in: starts real nodes')
class RoundTripTests(unittest.TestCase):
    """Send, hold, fetch, receipt, verify — one object, three nodes, nobody trusted."""

    @classmethod
    def setUpClass(cls):
        cls.lab = Path(tempfile.mkdtemp(prefix='dethron-'))
        (cls.lab/'object.bin').write_bytes(PAYLOAD)
        cls.ids = {name: cli('identity', name, cwd=cls.lab)
                   for name in ('relay', 'alice', 'bob')}
        cls.relay = subprocess.Popen(
            [sys.executable, '-m', 'dethron.cli', 'relay', 'relay', '--port', str(PORT)],
            cwd=str(cls.lab), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(12)
        cls.via = f"127.0.0.1:{PORT}/{cls.ids['relay']['propagation']}"

    @classmethod
    def tearDownClass(cls):
        cls.relay.terminate()
        try:
            cls.relay.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover - only on a wedged relay
            cls.relay.kill()
        shutil.rmtree(cls.lab, ignore_errors=True)

    def test_an_object_crosses_and_both_proofs_survive_the_sender_leaving(self):
        sent = cli('send', 'alice', 'object.bin', '--to', self.ids['bob']['contact'],
                   '--relay', self.via, '--relay-contact', self.ids['relay']['contact'],
                   cwd=self.lab)
        self.assertTrue(sent['proof_of_entry'], sent)
        self.assertEqual(sent['size'], len(PAYLOAD))

        # The sender is gone by now: its process ended with the send command.
        got = cli('fetch', 'bob', '--source', self.ids['alice']['contact'], '--relay', self.via,
                  '--receipt-to', self.ids['alice']['contact'], cwd=self.lab)
        self.assertTrue(got['completed'], got)
        self.assertEqual(got['sha256'], sent['sha256'])
        self.assertEqual((self.lab/'bob'/'output.bin').read_bytes(), PAYLOAD)

        back = cli('receipts', 'alice', '--relay', self.via, cwd=self.lab)
        self.assertEqual(back['collected'], 1, back)

        for who in ('bob', 'alice'):
            with self.subTest(node=who):
                report = cli('verify', who, cwd=self.lab)
                self.assertEqual(report['verdict'], 'pass', report)
                self.assertTrue(all(check['passed'] for check in report['checks']), report)

        alice = cli('verify', 'alice', cwd=self.lab)
        proves = {check.get('proves') for check in alice['checks']}
        self.assertEqual(proves, {'entry', 'exit'},
                         'the sender must end holding proof that it entered and that it left')


if __name__ == '__main__':
    unittest.main()
