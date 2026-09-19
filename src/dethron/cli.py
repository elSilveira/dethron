"""The command line: mint an identity, run a relay, send an object, fetch it, check the proofs.

Five commands are enough to exercise the whole claim, and none of them hides a step. `send`
returns a signed custody attestation or says why there is none. `fetch` returns the exact
bytes or says what is still missing. `verify` recomputes from the files on disk, trusting
nothing that any earlier command printed.

    dethron identity ./alice
    dethron relay ./relay --port 45810
    dethron send ./alice --to <contact> --relay <host:port/propagation> report.pdf
    dethron fetch ./bob --from <contact> --relay <host:port/propagation>
    dethron receipts ./alice --relay <host:port/propagation>
    dethron verify ./bob
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

from .node import Node, parse_contact, parse_relay

ANNOUNCE_SECONDS = 30


def show(**values):
    print(json.dumps(values, indent=2), flush=True)
    return 0


def identity(args):
    """An address is knowable before a node ever starts, so contacts can be exchanged first."""
    import RNS
    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    key = home/'identity'
    existed = key.exists()
    if existed:
        one = RNS.Identity.from_file(str(key))
    else:
        one = RNS.Identity()
        one.to_file(str(key))
    delivery = RNS.Destination.hash(one, 'lxmf', 'delivery').hex()
    return show(home=str(home), created=not existed,
                contact=f'{delivery}.{one.get_public_key().hex()}',
                propagation=RNS.Destination.hash(one, 'lxmf', 'propagation').hex())


def relay(args):
    """Hold objects for recipients who are not here yet, and attest to what is held."""
    with Node(args.home, relay=True, port=args.port, peers=args.peer, name='relay') as node:
        show(contact=node.contact, propagation=node.propagation,
             relay=f'<this host>:{args.port}/{node.propagation}')
        print('running; Ctrl-C to stop', file=sys.stderr, flush=True)
        try:
            while True:
                node.announce()
                time.sleep(ANNOUNCE_SECONDS)
        except KeyboardInterrupt:
            print('stopping', file=sys.stderr, flush=True)
    return 0


def send(args):
    """Hand an object to a relay and come back with proof that the relay took it."""
    from .parts import split
    from .protocol import data_envelope, encode
    endpoint, propagation = parse_relay(args.relay)
    destination, _ = parse_contact(args.to)
    content = Path(args.file).read_bytes()
    with Node(args.home, peers=[endpoint], name='origin') as node:
        node.announce()
        origin = node.source.hash.hex()
        part = split(content, 1, hashlib.sha256(content).hexdigest()[:32])[0]
        envelope = data_envelope(origin, destination, encode(part), int(time.time())+args.expires)
        handoff = node.send(encode(envelope), to=args.to, via=propagation, timeout=args.timeout)
        proof = node.custody_of(handoff['transient_id'], relay=args.relay_contact,
                                timeout=args.timeout) if args.relay_contact else None
        return show(contact=node.contact, size=len(content),
                    sha256=hashlib.sha256(content).hexdigest(),
                    transient_id=handoff['transient_id'], packed_bytes=handoff['packed_bytes'],
                    proof_of_entry=proof and proof['event'] == 'custody_received',
                    custody=proof)


def fetch(args):
    """Ask a relay for what it holds for us, reconstruct, and write a receipt."""
    endpoint, propagation = parse_relay(args.relay)
    with Node(args.home, receive=True, peers=[endpoint], name='recipient') as node:
        node.announce()
        state = node.fetch(source=args.source, via=propagation, timeout=args.timeout)
        receiver = state.get('receiver') or {}
        if receiver.get('completed') and args.receipt_to:
            node.publish_receipt(to=args.receipt_to, via=propagation, timeout=args.timeout)
        return show(contact=node.contact, completed=bool(receiver.get('completed')),
                    sha256=receiver.get('sha256'), output=str(Path(args.home)/'output.bin'),
                    sync=state.get('sync'), objects=receiver.get('objects'))


def receipts(args):
    """Come back after being away and collect the proofs a relay is holding for us."""
    endpoint, propagation = parse_relay(args.relay)
    with Node(args.home, peers=[endpoint], name='origin') as node:
        node.announce()
        state = node.collect(via=propagation, timeout=args.timeout)
        return show(contact=node.contact, collected=state['collected'],
                    receipts=state['receipts'], sync=state['sync'])


def verify(args):
    """Recompute the proofs held here. The checking itself lives in `audit`, on purpose:
    an auditor that shares a module with what it audits is a formality."""
    from .audit import verify_directory
    report = verify_directory(args.home)
    show(**report)
    return 0 if report['verdict'] != 'fail' else 1


def build_parser():
    parser = argparse.ArgumentParser(prog='dethron', description=__doc__.split('\n')[0])
    subs = parser.add_subparsers(dest='command', required=True)

    one = subs.add_parser('identity', help='mint or show a node identity and its contact')
    one.add_argument('home')
    one.set_defaults(run=identity)

    two = subs.add_parser('relay', help='hold objects for recipients who are not here yet')
    two.add_argument('home')
    two.add_argument('--port', type=int, required=True, help='TCP port to listen on')
    two.add_argument('--peer', action='append', default=[], help='host:port of another node')
    two.set_defaults(run=relay)

    three = subs.add_parser('send', help='hand an object to a relay and obtain proof of entry')
    three.add_argument('home')
    three.add_argument('file')
    three.add_argument('--to', required=True, help='the recipient contact')
    three.add_argument('--relay', required=True, help='host:port/<propagation address>')
    three.add_argument('--relay-contact', help="the relay's contact, to ask it for custody")
    three.add_argument('--expires', type=int, default=7200, help='seconds until the object expires')
    three.add_argument('--timeout', type=int, default=120)
    three.set_defaults(run=send)

    four = subs.add_parser('fetch', help='collect what a relay holds and reconstruct it')
    four.add_argument('home')
    four.add_argument('--source', required=True, help="the sender's contact")
    four.add_argument('--relay', required=True, help='host:port/<propagation address>')
    four.add_argument('--receipt-to', help="publish the receipt back to the sender's contact")
    four.add_argument('--timeout', type=int, default=180)
    four.set_defaults(run=fetch)

    six = subs.add_parser('receipts', help='collect the receipts a relay holds for us')
    six.add_argument('home')
    six.add_argument('--relay', required=True, help='host:port/<propagation address>')
    six.add_argument('--timeout', type=int, default=180)
    six.set_defaults(run=receipts)

    five = subs.add_parser('verify', help='recompute the proofs held in a node directory')
    five.add_argument('home')
    five.set_defaults(run=verify)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.run(args) or 0


if __name__ == '__main__':
    raise SystemExit(main())
