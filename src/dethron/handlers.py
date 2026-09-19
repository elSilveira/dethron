"""Everything that signs, verifies or keeps a proof. The node owns the transport; this
owns the evidence.

The split matters because these are the functions an adversary would want to be lax. A
relay attests only to what is really in its store. An origin accepts an answer only from
the key of the relay it asked, for the id it asked about. A receipt is kept only when it
is signed by a recipient this origin actually sent to. Each of those is a place where a
convenient shortcut would quietly turn a claim into a lie.
"""
import json
from pathlib import Path
import time

import LXMF
import RNS

from . import custody
from .protocol import APPLICATION, encode
from .wire import authenticate

STORE_WAIT = 10


def target_for(public_key, destination):
    RNS.Identity.remember(None, bytes.fromhex(destination), bytes.fromhex(public_key))
    peer = RNS.Identity(create_keys=False)
    peer.load_public_key(bytes.fromhex(public_key))
    return RNS.Destination(peer, RNS.Destination.OUT, RNS.Destination.SINGLE, 'lxmf', 'delivery')


def direct(node, public_key, destination, obj, label):
    """A direct message, used for the custody conversation while both ends are in contact."""
    message = LXMF.LXMessage(target_for(public_key, destination), node.source, encode(obj),
                             APPLICATION, desired_method=LXMF.LXMessage.DIRECT)
    message.register_delivery_callback(lambda m: node.emit('direct_delivered', label=label))
    message.register_failed_callback(lambda m: node.emit('direct_failed', label=label))
    node.router.handle_outbound(message)


def request_custody(node, relay, transient_id):
    """Origin side: ask one relay to attest that it holds one message."""
    destination, public_key = relay
    envelope = custody.request(node.source.hash.hex(), destination, transient_id,
                               node.identity.get_public_key().hex())
    node.expected[envelope['id']] = {'destination': destination, 'public_key': public_key,
                                     'transient_id': transient_id}
    direct(node, public_key, destination, envelope, f'request:{transient_id[:8]}')
    return {'request': envelope['id'], 'transient_id': transient_id}


def answer_custody(node, message):
    """Relay side: attest only what is really in the store; otherwise refuse explicitly."""
    known = RNS.Identity.recall(message.source_hash)
    req, key = custody.accept_request(message.packed, node.source.hash.hex(), time.time(),
                                      known.get_public_key() if known else None)
    tid, deadline = bytes.fromhex(req['transient_id']), time.monotonic()+STORE_WAIT
    while tid not in node.router.propagation_entries and time.monotonic() < deadline:
        time.sleep(.2)
    entry = node.router.propagation_entries.get(tid)
    if entry:
        reply = custody.attest(req, node.source.hash.hex(), entry[0].hex(),
                               Path(entry[1]).read_bytes(), entry[2])
    else:
        reply = custody.refuse(req, node.source.hash.hex(), 'transient id not in store')
    (node.custody/f"{req['transient_id']}.issued.json").write_text(json.dumps(reply), encoding='utf-8')
    node.emit('custody_answered', kind=reply['kind'], transient_id=req['transient_id'],
              requester=req['source'])
    direct(node, key.hex(), req['source'], reply, f"answer:{req['transient_id'][:8]}")


def collect_custody(node, message, kind):
    """Origin side: verify against the key of the relay we asked, then keep the packet."""
    asked = node.expected.get(custody.peek(message.packed, time.time()).get('id'))
    if asked is None:
        raise ValueError('unsolicited custody reply')
    key, tid = bytes.fromhex(asked['public_key']), asked['transient_id']
    if kind == 'custody':
        verified = custody.verify(message.packed, key, node.source.hash.hex(), tid, time.time())
        path = node.custody/f'{tid}.lxmf'
    else:
        verified = custody.verify_refusal(message.packed, key, node.source.hash.hex(), tid, time.time())
        path = node.custody/f'{tid}.refused.lxmf'
    path.write_bytes(message.packed)
    # The relay's contact travels beside the packet, so the attestation can be re-checked
    # later by somebody who was not here when it arrived.
    path.with_suffix('.relay').write_text(f"{asked['destination']}.{asked['public_key']}",
                                          encoding='utf-8')
    # Distinct from the request acknowledgement, which also carries the id.
    node.emit('custody_received' if kind == 'custody' else 'custody_refused',
              **{k: v for k, v in verified.items() if k not in ('version', 'kind')})


def remember_recipient(node, destination, public_key):
    """Whom the origin sent to must outlive the origin's process.

    The origin comes back as a new process after being offline, and a receipt arrives from
    a recipient it no longer remembers. Without this it rejects its own proof, which is
    the honest cost of verifiable delivery: the sender keeps what it expects to receive.
    """
    node.recipients[destination] = public_key
    (node.home/'recipients.json').write_text(json.dumps(node.recipients), encoding='utf-8')


def load_recipients(home):
    path = Path(home)/'recipients.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def collect_receipt(node, message):
    """Origin side: a receipt is only kept if signed by a recipient we actually sent to."""
    key = node.recipients.get(message.source_hash.hex())
    if key is None:
        raise ValueError('receipt from an unknown recipient')
    obj = authenticate(message.packed, bytes.fromhex(key), node.source.hash.hex(), time.time())
    if obj['kind'] != 'receipt':
        raise ValueError(f"expected a receipt: {obj['kind']}")
    (node.receipts/f"{obj['id']}.lxmf").write_bytes(message.packed)
    node.emit('receipt_received', **{k: v for k, v in obj.items() if k not in ('version', 'kind')})


def publish_receipt(node, origin, propagation, label='receipt'):
    """Recipient side: the local receipt travels back as a propagated message via one relay."""
    envelope = json.loads((node.home/'completion.json').read_text(encoding='utf-8'))
    destination, public_key = origin
    node.router.set_outbound_propagation_node(bytes.fromhex(propagation))
    message = LXMF.LXMessage(target_for(public_key, destination), node.source, encode(envelope),
                             APPLICATION, desired_method=LXMF.LXMessage.PROPAGATED)
    message.register_delivery_callback(lambda m: node.emit(
        'receipt_published', label=label, transient_id=m.transient_id.hex(),
        packed_bytes=len(m.packed)))
    message.register_failed_callback(lambda m: node.emit('send_failed', label=label))
    node.router.handle_outbound(message)
    return {'label': label, 'receipt_id': envelope['id']}
