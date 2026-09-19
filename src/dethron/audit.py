"""Recompute every proof a node directory holds, trusting nothing that produced it.

This is deliberately separate from the code that obtains proofs. An auditor that shares
its assumptions with the thing it audits is a formality. Everything here reads files and
checks signatures; it never asks a node what happened.

Each packet is checked inside the validity window it declared for itself. A proof that was
sound when it was made does not stop being sound when it expires, and a verifier that said
otherwise would quietly discard old evidence.
"""
import hashlib
import json
from pathlib import Path
import time

import RNS

from . import custody as attestation
from .endpoint import parse_contact
from .wire import authenticate, declared_expiry


def verify_directory(home):
    """Return a report: every check, whether it passed, and what it proves.

    The report is data, not a verdict to be taken on faith: each entry names the file it
    came from so a reader can repeat the check by hand.
    """
    home = Path(home)
    if not (home/'identity').exists():
        return {'home': str(home), 'verdict': 'nothing to verify',
                'hint': 'no identity here; run send or fetch in this directory first',
                'checks': []}
    identity = RNS.Identity.from_file(str(home/'identity'))
    mine = RNS.Destination.hash(identity, 'lxmf', 'delivery').hex()
    checks = _object(home)+_custody(home, mine)+_receipts(home, mine)
    if not checks:
        return {'home': str(home), 'verdict': 'nothing to verify', 'checks': [],
                'hint': 'no proofs here yet; run send or fetch in this directory first'}
    passed = all(check['passed'] for check in checks)
    return {'home': str(home), 'verdict': 'pass' if passed else 'fail', 'checks': checks}


def _object(home):
    """What was reconstructed must be what the receipt was issued over."""
    output, completion = home/'output.bin', home/'completion.json'
    if not (output.exists() and completion.exists()):
        return []
    envelope = json.loads(completion.read_text(encoding='utf-8'))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return [{'check': 'the reconstructed object matches the receipt issued for it',
             'passed': digest == envelope.get('digest'), 'file': output.name,
             'sha256': digest, 'bytes': output.stat().st_size}]


def _custody(home, mine):
    """Proof of entry: signed by the relay that was asked, for this message, to us."""
    checks = []
    for packet in sorted((home/'custody').glob('*.lxmf')) if (home/'custody').exists() else []:
        transient_id = packet.name.split('.')[0]
        refused = packet.name.endswith('.refused.lxmf')
        label = ('refusal' if refused else 'custody')+f' {transient_id[:8]}'
        sidecar = packet.with_suffix('.relay')
        if not sidecar.exists():
            checks.append({'check': f'{label} names the relay that signed it', 'passed': False,
                           'file': packet.name,
                           'error': 'no relay contact was recorded beside the packet'})
            continue
        raw = packet.read_bytes()
        try:
            _, key = parse_contact(sidecar.read_text(encoding='utf-8'))
            check = attestation.verify_refusal if refused else attestation.verify
            obj = check(raw, bytes.fromhex(key), mine, transient_id, declared_expiry(raw)-1)
            checks.append({'check': f'{label} is signed by the relay that was asked',
                           'passed': True, 'file': packet.name,
                           'proves': 'no entry' if refused else 'entry',
                           **{k: obj[k] for k in ('stored_size', 'reason') if k in obj}})
        except Exception as exc:
            checks.append({'check': label, 'passed': False, 'file': packet.name,
                           'error': repr(exc)})
    return checks


def _receipts(home, mine):
    """Proof of exit: signed by a recipient this node actually sent to, over these bytes."""
    path = home/'recipients.json'
    recipients = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    checks = []
    for packet in sorted((home/'receipts').glob('*.lxmf')) if (home/'receipts').exists() else []:
        raw, found = packet.read_bytes(), None
        for destination, key in recipients.items():
            try:
                found = (destination, authenticate(raw, bytes.fromhex(key), mine,
                                                   declared_expiry(raw)-1))
                break
            except Exception:
                continue
        if found is None:
            checks.append({'check': f'receipt {packet.stem[:8]} is signed by a known recipient',
                           'passed': False, 'file': packet.name,
                           'error': 'no recipient this node sent to could have signed it'})
            continue
        destination, obj = found
        checks.append({'check': f'receipt {packet.stem[:8]} is signed by the recipient sent to',
                       'passed': obj.get('kind') == 'receipt', 'file': packet.name,
                       'proves': 'exit', 'recipient': destination, 'digest': obj.get('digest')})
    return checks
