"""The delivery protocol: hand an object over, ask who is holding it, collect the proof.

The laboratory that produced this project's evidence drove its nodes through a file of
commands, which is right for a bench and wrong for a library. Here the calls are ordinary
and synchronous: `send` returns when the relay has taken the object, `custody_of` returns
the relay's signed attestation, `fetch` returns once the parts reconstruct. What is
asynchronous in LXMF is waited for here, with a deadline, and the wait is what the caller
would have had to write anyway.

Reachability and the record live in `endpoint.py`. This file is only about what is signed
and what is kept.
"""
import hashlib
import threading
import time

import LXMF
import RNS

from . import custody, handlers
from .endpoint import Endpoint, parse_contact, parse_relay
from .protocol import APPLICATION
from .receiver import Receiver

__all__ = ['Node', 'parse_contact', 'parse_relay']


class Node(Endpoint):
    """One node. Use it as a context manager so the router stops when the work ends."""

    def __init__(self, home, *, receive=False, **settings):
        super().__init__(home, **settings)
        self.receive, self.receiver = receive, None
        self.expected = {}
        self.recipients = handlers.load_recipients(self.home)

    def start(self):
        super().start()
        if self.receive:
            self.receiver = Receiver(self.home, self.source, 'split', self.emit)
        return self

    def on_delivery(self, message):
        """Every arriving message is either an object for us, or part of the proof exchange."""
        try:
            if self.receiver is not None:
                return self.receiver.receive(message)
            kind = custody.peek(message.packed, time.time())['kind']
            if kind == 'custody_request':
                threading.Thread(target=self._guarded,
                                 args=(handlers.answer_custody, message), daemon=True).start()
            elif kind in ('custody', 'custody_refusal'):
                handlers.collect_custody(self, message, kind)
            elif kind == 'receipt':
                handlers.collect_receipt(self, message)
            else:
                raise ValueError(f'unexpected message kind: {kind}')
        except Exception as exc:
            self.emit('rejected', error=repr(exc))

    def _guarded(self, function, *args):
        try:
            function(self, *args)
        except Exception as exc:
            self.emit('rejected', error=repr(exc))

    # ---- sending -------------------------------------------------------------------

    def send(self, payload, *, to, via, label='object', timeout=120):
        """Hand an object to a relay, and return once the relay has taken it."""
        destination, public_key = parse_contact(to)
        handlers.remember_recipient(self, destination, public_key)
        self.await_path(via, timeout=min(timeout, 60))
        self.router.set_outbound_propagation_node(bytes.fromhex(via))
        message = LXMF.LXMessage(handlers.target_for(public_key, destination), self.source,
                                 payload, APPLICATION, desired_method=LXMF.LXMessage.PROPAGATED)
        message.register_delivery_callback(lambda m: self.emit(
            'handoff', label=label, packed_bytes=len(m.packed),
            transient_id=m.transient_id.hex()))
        message.register_failed_callback(lambda m: self.emit('send_failed', label=label))
        self.router.handle_outbound(message)
        return self.wait('handoff', timeout, label=label)

    def custody_of(self, transient_id, *, relay, timeout=120):
        """Ask a relay to attest that it holds one message, and verify what comes back.

        A refusal is an answer too: it is signed, it names the message, and it is kept. An
        absent answer is not, which is why this raises rather than returning nothing.
        """
        contact = parse_contact(relay)
        self.await_path(contact[0], timeout=min(timeout, 60))
        handlers.request_custody(self, contact, transient_id)
        return self.wait_for(
            lambda row: row['event'] in ('custody_received', 'custody_refused')
            and row.get('transient_id') == transient_id,
            timeout, f'the relay never answered about {transient_id[:8]}')

    # ---- receiving -----------------------------------------------------------------

    def fetch(self, *, source, via, timeout=180, poll=2.0):
        """Ask a relay for whatever it holds for us, and wait for the object to reconstruct."""
        destination, public_key = parse_contact(source)
        RNS.Identity.remember(None, bytes.fromhex(destination), bytes.fromhex(public_key))
        self._ask(via, timeout)
        return self._until(lambda: (self.receiver.status() if self.receiver else {}).get('completed'),
                           timeout, poll, self.status)

    def publish_receipt(self, *, to, via, timeout=120):
        """Send the receipt back through a relay, so it can reach an origin that is away."""
        result = handlers.publish_receipt(self, parse_contact(to), via)
        return self.wait('receipt_published', timeout, label=result['label'])

    def collect(self, *, via, timeout=180, poll=2.0):
        """Come back later and pick up the receipts a relay is holding for us.

        This is the half of verifiable delivery that is easy to skip: the recipient signs,
        and the signature sits at a relay until the sender is reachable again. A sender
        that never comes back holds proof it can never read.
        """
        before = len(self.held_receipts())
        self._ask(via, timeout)
        self._until(lambda: len(self.held_receipts()) > before, timeout, poll, lambda: None)
        return {'receipts': self.held_receipts(), 'collected': len(self.held_receipts())-before,
                'sync': self.router.propagation_transfer_state}

    def _ask(self, via, timeout):
        self.await_path(via, timeout=min(timeout, 60))
        self.router.acknowledge_sync_completion(reset_state=True)
        self.router.set_outbound_propagation_node(bytes.fromhex(via))
        self.router.request_messages_from_propagation_node(self.identity)

    @staticmethod
    def _until(done, timeout, poll, final):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            if done():
                break
            time.sleep(poll)
        return final()

    # ---- state ---------------------------------------------------------------------

    def held_receipts(self):
        return sorted(p.name for p in self.receipts.glob('*.lxmf'))

    def status(self):
        files = [p for p in (self.home/'lxmf'/'messagestore').glob('*') if p.is_file()]
        return {'stored': len(self.router.propagation_entries),
                'sync': self.router.propagation_transfer_state,
                'inventory': sorted(hashlib.sha256(p.read_bytes()).hexdigest() for p in files),
                'custody': sorted(p.name for p in self.custody.glob('*')),
                'receipts': self.held_receipts(),
                'receiver': self.receiver.status() if self.receiver else None}
