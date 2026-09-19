"""Single XOR parity: two data shards plus parity, any two recover the object."""
import base64
import hashlib

from .parts import validate
from .protocol import encode


def parity_split(content, object_id):
    if not isinstance(content, bytes) or len(content) < 2:
        raise ValueError('need at least two bytes')
    width = (len(content)+1)//2
    left, right = content[:width], content[width:].ljust(width, b'\0')
    chunks = [left, right, bytes(a ^ b for a, b in zip(left, right))]
    manifest = {'version': 1, 'scheme': 'xor2', 'id': object_id, 'size': len(content),
                'digest': hashlib.sha256(content).hexdigest(), 'lengths': [width]*3,
                'hashes': [hashlib.sha256(c).hexdigest() for c in chunks]}
    parts = [{'manifest': manifest, 'index': i, 'data': base64.b64encode(c).decode()}
             for i, c in enumerate(chunks)]
    for part in parts:
        validate(encode(part))
    return parts


def reconstruct(manifest, chunks):
    if manifest['scheme'] == 'exact':
        if len(chunks) < len(manifest['lengths']):
            return None
        content = b''.join(chunks[i] for i in range(len(manifest['lengths'])))
    elif manifest['scheme'] == 'xor2':
        if len(chunks) < 2:
            return None
        chunks = dict(chunks)
        for index in (0, 1):
            if index not in chunks:
                chunks[index] = bytes(a ^ b for a, b in zip(chunks[1-index], chunks[2]))
        content = (chunks[0]+chunks[1])[:manifest['size']]
    else:
        raise ValueError('unsupported code')
    if len(content) != manifest['size'] or hashlib.sha256(content).hexdigest() != manifest['digest']:
        raise ValueError('whole object integrity mismatch')
    return content
