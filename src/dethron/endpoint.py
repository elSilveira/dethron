"""Being reachable: a Reticulum/LXMF endpoint that keeps a record of what passed through it.

This half knows nothing about custody or receipts. It starts a Reticulum instance in its
own directory, holds an identity, finds paths, and writes down what happened. The delivery
protocol is the other half, in `node.py`, and the split is there so that a change to how a
proof is signed cannot quietly change how the network is reached.

The record is not a log for humans. It is what an audit reads afterwards, and the reason a
claim about a run can be recomputed instead of believed.
"""
import json
import os
from pathlib import Path
import threading
import time

import LXMF
import RNS

from . import lxmf_stamp
from .config import config_text

DESTINATION_HEX, KEY_HEX = 32, 128


def parse_contact(text):
    """A contact is `<destination>.<public key>`, both hex: an address and the key that
    proves who answers at it. An address alone names a destination nobody can verify."""
    destination, _, key = str(text).strip().partition('.')
    if len(destination) != DESTINATION_HEX or len(key) != KEY_HEX:
        raise ValueError(f'a contact is {DESTINATION_HEX} hex characters, a dot, then {KEY_HEX}')
    bytes.fromhex(destination), bytes.fromhex(key)
    return destination, key


def parse_relay(text):
    """A relay is `<host>:<port>/<propagation address>`: where to dial and whom to ask."""
    endpoint, _, propagation = str(text).strip().partition('/')
    if len(propagation) != DESTINATION_HEX or ':' not in endpoint:
        raise ValueError('a relay is host:port/<propagation address>')
    bytes.fromhex(propagation)
    return endpoint, propagation


class Endpoint:
    """A node's reachability and its record. `Node` adds the delivery protocol on top."""

    def __init__(self, home, *, relay=False, port=None, peers=(), serial=None,
                 limit_kb=256, name=None, loglevel=3):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.relay, self.name = relay, name or self.home.name
        self.limit_kb, self.loglevel = limit_kb, loglevel
        self.config = config_text(port=port, peers=peers, serial=serial,
                                  transport=bool(serial and (port or peers)), loglevel=loglevel)
        self.custody = self.home/'custody'
        self.receipts = self.home/'receipts'
        self.events = self.home/'events.jsonl'
        self._rows, self._cond = [], threading.Condition()
        self.router = self.source = self.identity = None

    # ---- lifecycle -----------------------------------------------------------------

    def start(self):
        rns = self.home/'rns'
        rns.mkdir(exist_ok=True)
        (rns/'config').write_text(self.config, encoding='utf-8')
        for folder in (self.custody, self.receipts):
            folder.mkdir(exist_ok=True)
        # A stamp discarded by a logging line silently stops peering; install before the router.
        workaround = lxmf_stamp.install()
        RNS.Reticulum(configdir=str(rns), loglevel=self.loglevel, logdest=RNS.LOG_FILE)
        self.identity = self._identity()
        self.router = LXMF.LXMRouter(identity=self.identity, storagepath=str(self.home),
                                     autopeer=False, propagation_limit=2048,
                                     delivery_limit=self.limit_kb, sync_limit=8192,
                                     peering_cost=1, propagation_cost=1)
        self.source = self.router.register_delivery_identity(self.identity, display_name=self.name,
                                                             stamp_cost=None)
        if self.relay:
            self.router.enable_propagation()
        self.router.register_delivery_callback(self.on_delivery)
        self.emit('ready', stamp_workaround=workaround, pid=os.getpid(), contact=self.contact,
                  propagation=self.propagation)
        return self

    def _identity(self):
        """An identity belongs to its directory: the same folder is the same node, later."""
        key = self.home/'identity'
        if key.exists():
            return RNS.Identity.from_file(str(key))
        identity = RNS.Identity()
        identity.to_file(str(key))
        return identity

    def stop(self):
        if self.router is not None:
            self.router.exit_handler()
        self.emit('stopped')

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False

    def on_delivery(self, message):  # pragma: no cover - replaced by Node
        self.emit('delivered', size=len(message.packed))

    # ---- identity ------------------------------------------------------------------

    @property
    def contact(self):
        return f'{self.source.hash.hex()}.{self.identity.get_public_key().hex()}'

    @property
    def propagation(self):
        return self.router.propagation_destination.hash.hex()

    # ---- record --------------------------------------------------------------------

    def emit(self, event, **values):
        row = {'event': event, 'time': time.time(), **values}
        with self._cond:
            self._rows.append(row)
            self._cond.notify_all()
        with self.events.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n')
        return row

    def wait(self, event, timeout, **match):
        """Wait for one recorded event, or say plainly which one never came."""
        return self.wait_for(lambda row: row['event'] == event
                             and all(row.get(k) == v for k, v in match.items()),
                             timeout, f'no {event}')

    def wait_for(self, matches, timeout, missing):
        deadline = time.monotonic()+timeout
        with self._cond:
            while True:
                for row in self._rows:
                    if matches(row):
                        return row
                if not self._cond.wait(max(0.0, deadline-time.monotonic())):
                    raise TimeoutError(f'{self.name}: {missing} within {timeout}s')

    # ---- reachability --------------------------------------------------------------

    def await_path(self, destination, timeout=45):
        """Wait until this node knows how to reach an address, and say so when it never does.

        A message sent before a path exists is not slow, it is lost: the conversation would
        simply never happen, and the only symptom would be a timeout blaming the far end.
        Asking for the path first turns that into an honest error.
        """
        address = bytes.fromhex(destination)
        if not RNS.Transport.has_path(address):
            RNS.Transport.request_path(address)
        deadline = time.monotonic()+timeout
        while not RNS.Transport.has_path(address) and time.monotonic() < deadline:
            time.sleep(.5)
        if not RNS.Transport.has_path(address):
            raise TimeoutError(f'{self.name}: no path to {destination[:8]} within {timeout}s')
        return self.emit('path', destination=destination)

    def announce(self):
        if self.relay:
            self.router.announce_propagation_node()
        self.router.announce(self.source.hash)
        return self.emit('announced')
