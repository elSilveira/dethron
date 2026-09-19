# Dethron

Verifiable message delivery over [Reticulum](https://reticulum.network/) and LXMF.

**Guaranteed** delivery is impossible over intermittent contact: if the recipient never
appears, nothing reaches them. What is possible is knowing, with cryptographic proof and
without trusting the relay, which state a message is in.

| State | Proof | Who signs it |
| --- | --- | --- |
| **Entered** | A custody attestation naming the message, the recipient, and the bytes actually stored | the relay |
| **Pending** | A relay holding custody with no receipt: *awaiting contact* or *attested and not delivered* | derived, not claimed |
| **Left** | A receipt over the exact reconstructed bytes, which reaches the sender through any relay carrying it | the recipient |

A relay that attests and then discards the message is **named** by the absence of the
recipient's receipt. That is the point: nothing here asks you to trust an intermediary.

## Install

```
pip install dethron
```

Python 3.10 or newer. Reticulum and LXMF come with it.

## Try it

Three terminals, or one and some patience. Everything below is real: real Reticulum
instances, real LXMF propagation, real signatures.

```bash
# 1. Mint three identities and note their contacts
dethron identity ./relay
dethron identity ./alice
dethron identity ./bob

# 2. Run a relay, which holds objects for recipients who are not here yet
dethron relay ./relay --port 45810
```

With the relay running, and using the `contact` and `propagation` values it printed:

```bash
# 3. Alice hands an object to the relay and comes back with proof it was taken
dethron send ./alice report.pdf \
  --to <bob's contact> \
  --relay 127.0.0.1:45810/<relay propagation> \
  --relay-contact <relay's contact>

# 4. Bob, who was not around for any of that, collects and reconstructs it
dethron fetch ./bob \
  --source <alice's contact> \
  --relay 127.0.0.1:45810/<relay propagation> \
  --receipt-to <alice's contact>

# 5. Alice comes back later and picks up the receipt Bob signed
dethron receipts ./alice --relay 127.0.0.1:45810/<relay propagation>

# 6. Either of them recomputes every proof from the files on disk
dethron verify ./alice
```

`verify` ends with both halves of the claim:

```json
{
  "verdict": "pass",
  "checks": [
    { "check": "custody 10019ad5 is signed by the relay that was asked",
      "passed": true, "proves": "entry", "stored_size": 18688 },
    { "check": "receipt 02377a24 is signed by the recipient sent to",
      "passed": true, "proves": "exit",
      "digest": "02377a2438d3a5ab8f90f2bbc0cf67f16d8f1ce89da2d867dec1fc4ea2389070" }
  ]
}
```

Alice and Bob were never online at the same time.

## As a library

```python
from dethron import Node

with Node('./alice', peers=['relay.example:45810']) as node:
    handoff = node.send(payload, to=bob_contact, via=relay_propagation)
    proof = node.custody_of(handoff['transient_id'], relay=relay_contact)
```

Calls are synchronous: `send` returns once the relay has taken the object, `custody_of`
returns the relay's signed attestation, `fetch` returns once the parts reconstruct. Each
node writes an `events.jsonl` beside itself — not a log for humans, but the record an
audit reads afterwards.

## What is proved, and what is not

The claims come with artifacts, in [`evidence/`](evidence/README.md), and with documents
stating the controls that had to fail: see [`docs/`](docs/).

Proved, within a declared scope:

- Custody, pendency and receipt return ([V1](docs/V1_CUSTODY.md), [receipt](docs/V1_RECEIPT_RETURN.md)).
- Reproduction on an independent machine following the document alone ([V2](docs/V2_REPRODUCTION.md)).
- An object crossing between two distinct machines over a link carrying **no IP**,
  with the recipient proved to hold no IP interface ([V3c](docs/V3C_BENCH.md)).

Not proved, and not claimed:

- **Scale.** One message, one relay, one recipient. No numbers for many peers or a queue.
- **Key exchange and discovery.** Contacts are exchanged out of band, by you.
- **A hostile relay in the wild.** The refusals are tested; the adversary is simulated.
- **Long offline periods.** The sessions in the evidence are disjoint by seconds, not days.
- Everything the milestone documents list under "Limits", which is where to look first.

## Contributing

Bug reports and reproductions are the most useful thing you can send. See
[CONTRIBUTING.md](CONTRIBUTING.md). The house rule is that a claim arrives with the
control that would have caught it being wrong.

## Where the evidence came from

The bench that produced it — generations of nodes, cut media, two-machine schedules, the
auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research),
along with the deliberation and the runs that failed. This repository is the part that is
meant to be used; that one is the part that is meant to be checked.

## Licence

[Apache 2.0](LICENSE). Reticulum and LXMF are dependencies under their own licences; this
work imports them, it does not derive from them.
