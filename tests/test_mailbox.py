from pathlib import Path
import tempfile
import unittest

from dethron.mailbox import Mailbox
from dethron.protocol import data_envelope, receipt_envelope


class MailboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.message = data_envelope("a"*32, "b"*32, b"hello", 100, "c"*32)
        self.sender = Mailbox(self.path / "sender.db", "a"*32)
        self.receiver = Mailbox(self.path / "receiver.db", "b"*32)

    def test_handoff_is_not_confirmation_and_valid_receipt_is(self):
        self.sender.queue(self.message, 10)
        key = self.sender.pending(10)[0]["key"]
        self.sender.begin_attempt(key, 10)
        self.sender.handoff(key)
        self.assertEqual(self.sender.snapshot()[0]["state"], "handed_off")
        self.sender.accept_verified(receipt_envelope(self.message), b"signed receipt", 11)
        self.sender.handoff(key)
        self.assertEqual(self.sender.snapshot()[0]["state"], "confirmed")

    def test_receive_is_idempotent_and_receipt_is_persisted_together(self):
        self.assertTrue(self.receiver.accept_verified(self.message, b"wire", 10))
        self.assertFalse(self.receiver.accept_verified(self.message, b"wire2", 10))
        rows = self.receiver.snapshot()
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(r["state"] == "received" for r in rows), 1)
        self.assertEqual(self.receiver.pending(10)[0]["envelope"]["kind"], "receipt")

    def test_same_id_different_content_does_not_replace_received_data(self):
        self.receiver.accept_verified(self.message, b"wire", 10)
        conflict = data_envelope("a"*32, "b"*32, b"wrong", 100, "c"*32)
        with self.assertRaises(ValueError):
            self.receiver.accept_verified(conflict, b"wire", 10)
        self.assertEqual(len(self.receiver.snapshot()), 2)

    def test_wrong_receipts_do_not_confirm(self):
        self.sender.queue(self.message, 10)
        receipt = receipt_envelope(self.message)
        for change in ({"source": "d"*32}, {"id": "d"*32}, {"digest": "0"*64}, {"expires": 99}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.sender.accept_verified({**receipt, **change}, b"wire", 11)
        self.assertEqual(self.sender.snapshot()[0]["state"], "queued")

    def test_capacity_failure_rolls_back_inbox_and_receipt(self):
        limited = Mailbox(self.path / "limited.db", "b"*32, max_rows=1)
        with self.assertRaises(ValueError):
            limited.accept_verified(self.message, b"wire", 10)
        self.assertEqual(limited.snapshot(), [])
        tiny = Mailbox(self.path / "tiny.db", "a"*32, max_bytes=10)
        with self.assertRaises(ValueError):
            tiny.queue(self.message, 10)
        self.assertEqual(tiny.snapshot(), [])

    def test_retry_budget_and_expiry_are_persistent(self):
        self.sender.queue(self.message, 10)
        for _ in range(3):
            item = self.sender.pending(10)[0]
            self.sender.begin_attempt(item["key"], 10)
        self.assertEqual(self.sender.pending(10), [])
        reopened = Mailbox(self.path / "sender.db", "a"*32)
        self.assertEqual(reopened.pending(10), [])
        self.assertEqual(reopened.pending(100), [])
        self.assertEqual(reopened.snapshot()[0]["state"], "expired")

    def test_database_cannot_silently_change_identity(self):
        with self.assertRaises(ValueError):
            Mailbox(self.path / "sender.db", "e"*32)


if __name__ == "__main__":
    unittest.main()
