"""Verifiable message delivery over Reticulum and LXMF.

Guaranteed delivery is impossible over intermittent contact: if the recipient never
appears, nothing reaches them. What is possible is knowing, with cryptographic proof and
without trusting the relay, which state a message is in — it entered the network, it is
pending at a named relay, or the recipient signed for it.

    from dethron import Node

    with Node('./alice', peers=['relay.example:45810']) as node:
        handoff = node.send(payload, to=recipient, via=relay_propagation)
        proof = node.custody_of(handoff['transient_id'], relay=relay_contact)

`proof` is the relay's signature over the message it is holding, for that recipient. It
proves entry, not delivery: only the recipient's receipt proves exit, and a relay that
attests and then discards is named by the absence of that receipt.
"""
from . import custody
from .audit import verify_directory
from .endpoint import Endpoint
from .node import Node, parse_contact, parse_relay
from .protocol import data_envelope, decode, encode, receipt_envelope
from .wire import authenticate, declared_expiry

__version__ = '0.1.0'
__all__ = ['Endpoint', 'Node', 'authenticate', 'custody', 'data_envelope', 'decode',
           'declared_expiry', 'encode', 'parse_contact', 'parse_relay', 'receipt_envelope',
           'verify_directory']
