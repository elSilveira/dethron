"""Bounded application mailbox, independent from the native LXMF propagation store."""
from contextlib import contextmanager
import sqlite3

from .protocol import encode


def row_key(direction, obj):
    return "/".join([direction, obj["source"], obj["destination"], obj["id"], obj["kind"]])


class Database:
    def __init__(self, path, identity, max_rows=128, max_bytes=8*1024*1024):
        self.path, self.identity = path, identity
        self.max_rows, self.max_bytes = max_rows, max_bytes
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (identity TEXT, version INTEGER)")
            row = db.execute("SELECT identity,version FROM metadata").fetchone()
            if row and tuple(row) != (identity, 1):
                raise ValueError("mailbox identity/schema mismatch")
            if not row:
                db.execute("INSERT INTO metadata VALUES (?,1)", (identity,))
            db.execute("""CREATE TABLE IF NOT EXISTS messages (
                key TEXT PRIMARY KEY, direction TEXT, body BLOB NOT NULL,
                state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                wire BLOB NOT NULL DEFAULT X'')""")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def insert(self, db, direction, obj, state, wire=b""):
        key, body = row_key(direction, obj), encode(obj)
        existing = db.execute("SELECT body FROM messages WHERE key=?", (key,)).fetchone()
        if existing:
            if existing["body"] != body:
                raise ValueError("message ID conflicts with persisted content")
            return False
        count, used = db.execute("SELECT COUNT(*), COALESCE(SUM(length(body)+length(wire)),0) FROM messages").fetchone()
        if count >= self.max_rows or used+len(body)+len(wire) > self.max_bytes:
            raise ValueError("mailbox capacity exceeded")
        db.execute("INSERT INTO messages(key,direction,body,state,wire) VALUES (?,?,?,?,?)",
                   (key, direction, body, state, wire))
        return True
