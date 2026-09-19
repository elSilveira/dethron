# G1 — a persistent message and an authenticated confirmation

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

Closed: 16/09/2026. Predecessor: [G0](G0_REFERENCE.md).
Plan: [architecture and milestones](https://github.com/elSilveira/dethron-research/blob/master/DETHRON_MASTER_PLAN.md).

## Assessment before investing

**G0 was satisfactory for a limited integration.** Its re-audit confirmed three objects
received after restarts, with valid signature and content. That demonstrated no novelty
from Dethron: it showed that Reticulum/LXMF can be built upon. The investment authorised
for G1 was a small application boundary, needed in order to test messages made of parts
afterwards.

**G1's question:** can we hold a delivery obligation across restarts, without confusing
sending with confirmation, without duplicating the received message, and without
accepting a confirmation from another participant?

## Implementation and architecture decision

The [dethron_gateway](../src/dethron/__init__.py) package, in Python, next to the
native Reticulum 1.5.4/LXMF 1.1.1 API. The Rust v2 recovery core stays separate. This
choice changes the proposal of putting every early transition in Rust: the integration
and the application's mailbox are validated first in the reference's own language,
avoiding a second implementation and a cross-language bridge before the need is
measured. It is not a migration of the v2 core.

| Component | Responsibility |
| --- | --- |
| `protocol.py` | A versioned manifest for a whole object; ids, endpoints, size, SHA-256, deadline and a bounded payload |
| `wire.py` | Check the native LXMF signature and bind the manifest to the effective origin and destination |
| `database.py` | SQLite, transactions, database identity and admission by capacity |
| `mailbox.py` | Outbox, inbox, receipts, deduplication, attempts and expiry |
| `adapter.py` | Real send/receive integration with LXMF; explicit progress through `pump()` |
| `g1_node.py` | Laboratory process, persistent identity and JSONL control |
| `g1_scenario.py` / `run_g1_probe.py` | Failure schedule, execution and re-audit of the databases and packets |

The store in `v2/src/network/node_store.rs` persists opaque units in files, but does not
offer the joint transaction of inbox and receipt this slice requires. So the mailbox uses
SQLite, `journal_mode=DELETE`, `synchronous=FULL` and `BEGIN IMMEDIATE`: the message and
the pending receipt enter in the same transaction. The tests cover a process crash
before and after the commit; they do not validate power loss or hardware failure.
[SQLite's semantics and assumptions](https://www.sqlite.org/atomiccommit.html).

No new cryptography was created. The manifest travels inside LXMF, encrypted by the
native transport and signed by the sending identity. Verification uses Ed25519 from
`cryptography` and the native format; it does not rely on a success flag alone. The
laboratory databases and keys sit on disk **with no additional protection at rest**.

## Contract and states

The minimal reusable API:

- `Mailbox.queue(envelope, now)`: admits a local message and persists before returning.
- `Mailbox.pending(now)`: lists the eligible ones and marks expiry; it does not transmit.
- `Adapter.pump()`: submits pending items to LXMF; the calling schedule belongs to the
  caller.
- `Adapter.receive(message)`: authenticates, validates and applies the local transaction.
- `Mailbox.snapshot()`: queries states, attempts and references.

`accept_verified()` is an internal trust boundary: it must only receive objects already
authenticated by the adapter. A hash on its own does not authenticate a sender.

```text
origin: queued -> sending -> handed_off
                          -> confirmed, only with a valid receipt from the destination
        pending items without confirmation -> expired on reaching the deadline

destination: validate -> [inbox received + receipt queued] in the same transaction
                      -> transmit the receipt over LXMF
```

A receipt binds version, id, origin and destination inverted, size, digest and deadline.
A valid signature from another identity does not confirm the obligation. A late handoff
callback does not demote `confirmed`. Resending with the same id and content keeps a
single inbox entry; the same id with different content is rejected.

A duplicate may requeue the receipt, preserving its attempt limit. This does not
guarantee exactly-once execution of external effects such as a payment. A receipt means
this implementation persisted the message before signing it; signatures from dishonest
participants are not economic proof of service.

## Frozen laboratory profile

| Item | Value |
| --- | --- |
| Medium | Loopback TCP, one Windows host; direct LXMF delivery, no propagation node in this slice |
| Participants | O sends; D receives; X tries to confirm with another identity; one further identity never has a process |
| Positive message | 65,536 deterministic SHAKE-256 bytes; expiry in 180 s |
| Negative | A recipient with no known identity or local route; expiry in 30 s; no confirmation |
| Application limits | 1 MiB of payload; 1,500,000 bytes of JSON envelope; 128 records; 8 MiB logical of stored bodies and packets |
| Attempts | Up to 3 submissions per obligation to the adapter, persisted across restarts |
| Crashes | `os._exit(23)`, preserving disk and identity |
| Evidence | Local databases, signed LXMF packets, manifest, logs, timeline, versions and source hashes recorded |

The attempt limit does not count LXMF's internal retransmissions. The logical quota
measures no physical footprint and does not bound every cache or log of the library. Old
records are kept: there is no automatic collection and no production retention policy;
on reaching capacity, admission fails explicitly. The local UTC clock is trusted; a clock
rollback has not been validated.

This round's negative sends no payload to an intermediary: the absent identity is not
known, stays pending and expires. This complements G0's negative, which really did store
the absent destination's message at a propagation node.

## Tests and satisfaction criteria

| Test | Criterion |
| --- | --- |
| The origin crashes before transmitting | The queue and the identity survive; a later send uses the persisted record |
| The destination crashes after the commit and before the receipt | Inbox and receipt survive together |
| A crash inside the transaction, before the commit | No partial inbox and no persisted receipt; tested in a real subprocess |
| Retransmission after a restart | One logical entry; the duplicate identified |
| Handoff without a receipt | The origin stays unconfirmed |
| X sends a receipt with its own valid signature | Rejected; no confirmation |
| A corrupted manifest signed and sent over LXMF | Rejected at the receiver |
| The legitimate receipt returns; the origin restarts | `confirmed` persists; the re-audit checks the destination's signature |
| An absent recipient | Expires with no receipt and no confirmation |
| Insufficient capacity | Admission fails and inbox and receipt are undone together |
| Invalid version, fields, signature, endpoint or content | Rejected in the contract and authentication tests |
| The auditor receives a tampered obligation or deadline | It does not accept, even where a valid signature exists |

The fast tests use synthetic inputs; one boundary test uses a stand-in router to
reproduce the cached-route regression. Those tests are not counted as network proof. The
integration run uses real processes and real LXMF.

## Reproduction

At the repository root, with the [environment pinned in G0](G0_REFERENCE.md#reproduction):

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_g1_*.py'
$env:RUN_GATEWAY_G1='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_g1_reference.py
Remove-Item Env:RUN_GATEWAY_G1
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g1
```

To follow the events: `window/.venv-gateway/Scripts/python.exe window/run_g1_probe.py`.
Each round creates `window/results/gateway-g1-ID`, overwriting no attempt. Local
artifacts contain private keys and laboratory content and are ignored by Git. The
documentary summary preserves the result and the limits for other installations.

## Rounds and final assessment

| Round | Result |
| --- | --- |
| `1789498739568561700` | Inconclusive: the adapter demanded a cached route and blocked the native return channel. The error was reproduced in a test and fixed by delegating path choice to LXMF. |
| `1789498865120420300` | The integration passed in 30.230 s; persistent confirmation, duplicate, corruption and wrong identity all checked. |
| `1789581740304500500` | The final version passed in 31.124 s, with a hardened auditor and a re-audit of the databases and packets. |

[First approved report](../evidence/gateway-g1-1789498865120420300/report.json). The later
review hardened the auditor to compare every field of the obligation and to close SQLite
connections explicitly; the final version was repeated before closing.

[Final report](../evidence/gateway-g1-1789581740304500500/report.json),
[manifest](../evidence/gateway-g1-1789581740304500500/manifest.json) and
[timeline](../evidence/gateway-g1-1789581740304500500/timeline.jsonl).
The G0 regression with the shared launcher also passed:
[report](../evidence/gateway-g0-1789498911484614700/report.json).

Final checks:

- **19 fast G1 tests passed** in the `.venv-gateway` environment; the opt-in run was
  skipped in that call and executed separately: **1 real integration passed**.
- General suite: **136 passed, 7 skipped**. The skips are the five modules depending on
  the RNS/LXMF environment plus the two opt-in network runs; the G1 execution and the G0
  regression are recorded separately above. The fast G0 tests had already passed when G0
  closed.
- The source hashes match the final round; new modules and tests are under 200 lines;
  the documentation's local links were checked.
- The two functional rounds are development evidence, with no statistical estimate of
  reliability, energy benefit or performance gain.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**: the pre-Dethron work left the tree when the repository was prepared for
publication.

**Decision:** satisfactory as a functional laboratory integration; not as a
production-ready network and not as a demonstration of competitive advantage. There is a
reason for a small G2: to test whether parts arriving from incomplete contacts add
usefulness on a comparable budget. G2 is not approved in advance.

G2 must compare, with the same contacts and limits, whole objects, exact parts and then
an established encoding. If the gain disappears once metadata, retransmissions and
storage are counted, keep the integration alone or close the own-protocol hypothesis. Do
not widen to a physical mesh, tokens or global scale to compensate for an absent gain.

G1 does not test the application receipt crossing offline propagation nodes; G0 and G1
proved separate parts. That composition, radio, a physically full disk, persistent
attacks, key rotation and operation without a supervisor all remain pending.
