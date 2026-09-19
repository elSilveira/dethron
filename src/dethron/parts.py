"""Exact parts, without erasure coding. Each descriptor is inside authenticated G1 data."""
import base64
import hashlib
import json
import re

from .protocol import MAX_PAYLOAD, _unique, encode


def split(content, count, object_id):
    if type(count) is not int or not 1 <= count <= 32 or not count <= len(content) <= MAX_PAYLOAD:
        raise ValueError("invalid split bounds")
    pieces = [content[len(content)*i//count:len(content)*(i+1)//count] for i in range(count)]
    manifest = {"version": 1, "scheme": "exact", "id": object_id, "size": len(content),
                "digest": hashlib.sha256(content).hexdigest(), "lengths": list(map(len, pieces)),
                "hashes": [hashlib.sha256(p).hexdigest() for p in pieces]}
    result = [{"manifest": manifest, "index": i, "data": base64.b64encode(p).decode()}
              for i, p in enumerate(pieces)]
    for part in result:
        validate(encode(part))
    return result


def validate(raw):
    try:
        if not isinstance(raw, bytes) or len(raw) > MAX_PAYLOAD:
            raise ValueError("oversized part descriptor")
        obj = json.loads(raw, object_pairs_hook=_unique)
        if set(obj) != {"manifest", "index", "data"}:
            raise ValueError("invalid part fields")
        m = obj["manifest"]
        if set(m) != {"version", "scheme", "id", "size", "digest", "lengths", "hashes"}:
            raise ValueError("invalid manifest fields")
        if type(m["version"]) is not int or m["version"] != 1 or m["scheme"] not in ("exact", "xor2"):
            raise ValueError("unsupported manifest")
        if not re.fullmatch("[0-9a-f]{32}", m["id"]):
            raise ValueError("invalid object ID")
        lengths, hashes = m["lengths"], m["hashes"]
        if not isinstance(lengths, list) or not isinstance(hashes, list) or not 1 <= len(lengths) == len(hashes) <= 32:
            raise ValueError("invalid part count")
        if any(type(n) is not int or n <= 0 for n in lengths):
            raise ValueError("invalid part lengths")
        if type(m["size"]) is not int or not 1 <= m["size"] <= MAX_PAYLOAD:
            raise ValueError("invalid total size")
        if m['scheme'] == 'exact' and sum(lengths) != m['size']:
            raise ValueError('invalid exact lengths')
        if m['scheme'] == 'xor2' and (m['size'] < 2 or lengths != [(m['size']+1)//2]*3):
            raise ValueError('invalid parity lengths')
        if any(not re.fullmatch("[0-9a-f]{64}", h) for h in hashes+[m["digest"]]):
            raise ValueError("invalid digest")
        index = obj["index"]
        if type(index) is not int or not 0 <= index < len(lengths):
            raise ValueError("invalid part index")
        content = base64.b64decode(obj["data"], validate=True)
        if len(content) != lengths[index] or hashlib.sha256(content).hexdigest() != hashes[index]:
            raise ValueError("part integrity mismatch")
        return m, index, content
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("invalid part descriptor") from exc
