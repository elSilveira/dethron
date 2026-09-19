"""Transactional partial assembly with bounded retained evidence."""
import base64
from contextlib import contextmanager
import hashlib
import json
import sqlite3

from .parts import validate
from .erasure import reconstruct
from .protocol import decode, encode


class Assembly:
    def __init__(self, path, identity, max_bytes=8*1024*1024):
        self.path, self.identity, self.max_bytes = path, identity, max_bytes
        with self.transaction() as db:
            db.execute("CREATE TABLE IF NOT EXISTS owner(identity TEXT,version INTEGER)")
            owner = db.execute("SELECT * FROM owner").fetchone()
            if owner and owner != (identity, 1):
                raise ValueError("assembly identity/schema mismatch")
            if not owner:
                db.execute("INSERT INTO owner VALUES (?,1)", (identity,))
            db.execute("CREATE TABLE IF NOT EXISTS objects(key TEXT PRIMARY KEY,manifest BLOB,expires INTEGER,result BLOB)")
            db.execute("CREATE TABLE IF NOT EXISTS parts(key TEXT,idx INTEGER,data BLOB,wire BLOB,PRIMARY KEY(key,idx))")

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
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

    def accept_verified(self, envelope, wire, now):
        obj = decode(encode(envelope), now)
        if obj["kind"] != "data" or obj["destination"] != self.identity:
            raise ValueError("not local authenticated data")
        manifest, index, content = validate(base64.b64decode(obj["payload"], validate=True))
        key = "/".join([obj["source"], obj["destination"], manifest["id"]])
        encoded = encode(manifest)
        with self.transaction() as db:
            existing = db.execute("SELECT manifest,expires FROM objects WHERE key=?", (key,)).fetchone()
            if existing and existing != (encoded, obj["expires"]):
                raise ValueError("incompatible manifest or lifetime")
            if not existing:
                if db.execute("SELECT count(*) FROM objects").fetchone()[0] >= 16:
                    raise ValueError("object count limit")
                db.execute("INSERT INTO objects VALUES (?,?,?,NULL)", (key, encoded, obj["expires"]))
            previous = db.execute("SELECT data FROM parts WHERE key=? AND idx=?", (key, index)).fetchone()
            fresh = previous is None
            if previous and previous[0] != content:
                raise ValueError("conflicting part")
            if fresh:
                db.execute("INSERT INTO parts VALUES (?,?,?,?)", (key, index, content, wire))
            chunks = dict(db.execute("SELECT idx,data FROM parts WHERE key=? ORDER BY idx", (key,)))
            joined = reconstruct(manifest, chunks)
            complete = joined is not None
            if complete:
                db.execute("UPDATE objects SET result=? WHERE key=?", (joined, key))
            used = db.execute("SELECT COALESCE(SUM(length(manifest)+COALESCE(length(result),0)),0) FROM objects").fetchone()[0]
            used += db.execute("SELECT COALESCE(SUM(length(data)+length(wire)),0) FROM parts").fetchone()[0]
            if used > self.max_bytes:
                raise ValueError("assembly capacity exceeded")
            return {"key": key, "id": manifest["id"], "count": len(chunks), "complete": complete,
                    "fresh": fresh, "digest": manifest["digest"], "size": manifest["size"]}

    def content(self, key):
        with self.transaction() as db:
            row = db.execute("SELECT result FROM objects WHERE key=?", (key,)).fetchone()
            return row[0] if row else None

    def snapshot(self):
        with self.transaction() as db:
            result = []
            for key, raw, content in db.execute("SELECT key,manifest,result FROM objects"):
                m = json.loads(raw)
                count = db.execute("SELECT count(*) FROM parts WHERE key=?", (key,)).fetchone()[0]
                result.append({"id": m["id"], "count": count, "complete": content is not None})
            return result
