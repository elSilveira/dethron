"""Transactional states. Only the transport boundary may call accept_verified."""
import json

from .database import Database, row_key
from .protocol import decode, encode, receipt_envelope


class Mailbox(Database):
    MAX_ATTEMPTS = 3

    def queue(self, envelope, now):
        obj = decode(encode(envelope), now)
        if obj["kind"] != "data" or obj["source"] != self.identity:
            raise ValueError("only local data can be submitted")
        with self.transaction() as db:
            return self.insert(db, "out", obj, "queued")

    def accept_verified(self, envelope, wire, now, after_inbox=None):
        obj = decode(encode(envelope), now)
        if obj["destination"] != self.identity:
            raise ValueError("wrong local destination")
        with self.transaction() as db:
            if obj["kind"] == "receipt":
                original = {**obj, "source": obj["destination"],
                            "destination": obj["source"], "kind": "data"}
                key = row_key("out", original)
                row = db.execute("SELECT body,wire FROM messages WHERE key=?", (key,)).fetchone()
                if not row or receipt_envelope(json.loads(row["body"])) != obj:
                    raise ValueError("receipt does not match an outgoing obligation")
                used = db.execute("SELECT COALESCE(SUM(length(body)+length(wire)),0) FROM messages").fetchone()[0]
                if used-len(row["wire"])+len(wire) > self.max_bytes:
                    raise ValueError("mailbox capacity exceeded")
                db.execute("UPDATE messages SET state='confirmed',wire=? WHERE key=?", (wire, key))
                return True
            fresh = self.insert(db, "in", obj, "received", wire)
            if after_inbox:
                after_inbox(db)  # Fault-injection seam; runs inside the transaction, before commit.
            receipt = receipt_envelope(obj)
            self.insert(db, "out", receipt, "queued")
            # Repeat delivery can recover a lost receipt, but cannot reset the retry budget.
            db.execute("UPDATE messages SET state='queued' WHERE key=? AND attempts<?",
                       (row_key("out", receipt), self.MAX_ATTEMPTS))
            return fresh

    def pending(self, now):
        result = []
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM messages WHERE direction='out'").fetchall():
                obj = json.loads(row["body"])
                if row["state"] in ("confirmed", "expired"):
                    continue
                if obj["expires"] <= now:
                    db.execute("UPDATE messages SET state='expired' WHERE key=?", (row["key"],))
                    continue
                eligible = obj["kind"] == "data" or row["state"] != "handed_off"
                if eligible and row["attempts"] < self.MAX_ATTEMPTS:
                    result.append({"key": row["key"], "envelope": obj})
        return result

    def begin_attempt(self, key, now):
        with self.transaction() as db:
            row = db.execute("SELECT * FROM messages WHERE key=?", (key,)).fetchone()
            if not row or row["direction"] != "out" or row["state"] in ("confirmed", "expired"):
                raise ValueError("not an outgoing pending message")
            if row["attempts"] >= self.MAX_ATTEMPTS or json.loads(row["body"])["expires"] <= now:
                raise ValueError("retry budget exhausted or expired")
            db.execute("UPDATE messages SET state='sending',attempts=attempts+1 WHERE key=?", (key,))

    def handoff(self, key):
        with self.transaction() as db:
            db.execute("UPDATE messages SET state='handed_off' WHERE key=? AND state='sending'", (key,))

    def snapshot(self):
        with self.transaction() as db:
            result = []
            for row in db.execute("SELECT * FROM messages ORDER BY key"):
                obj = json.loads(row["body"])
                result.append({"id": obj["id"], "kind": obj["kind"], "direction": row["direction"],
                               "destination": obj["destination"], "digest": obj["digest"],
                               "state": row["state"], "attempts": row["attempts"]})
            return result
