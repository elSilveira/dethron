# V1 — receipt return: the proof of exit reaches an origin never online with the destination

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

17/09/2026. The second half of milestone V1 of [version 7 of the plan](https://github.com/elSilveira/dethron-research/blob/master/DETHRON_MASTER_PLAN.md),
over Reticulum 1.5.4/LXMF 1.1.1. The first half, custody and pendency, is in
[V1_CUSTODY.md](V1_CUSTODY.md). Together they close what the plan calls verifiable
delivery.

## What is proved here

Up to the first half, the recipient's receipt was produced locally on `D` and never
reached whoever sent the message. This slice tests hypothesis H20: **the receipt reaches
the origin in a useful fraction of cases without origin and destination being reachable
at the same time.** Non-simultaneity is the central control — without it, any direct
delivery would pass as a return.

What is proved is narrow and is stated as such: when delivery happened, the proof exists
at the destination and is obtained by the origin from **any relay carrying a copy**.
When no visited relay carries it, that appears as **proof pendency**, distinct from
delivery pendency. When delivery did not happen, no proof exists anywhere — and nothing
resembling one can appear.

## LXMF facts confirmed in the installed source

- The outbound propagation node is read **in the queue's asynchronous processing**, not
  when the message is handed to the router (LXMRouter.py, lines 2849–2860). Publishing
  the receipt to three relays requires a sequence: point, send, wait for the handoff,
  next. Three sends in a row with different nodes would all go to the last one pointed at.
- The origin's fetch uses exactly the recipient's fetch path:
  `request_messages_from_propagation_node(identity)` identifies the origin on the link
  and asks for the messages for its delivery destination (lines 502–514).

## Design

1. On completion, `D` writes the receipt envelope to `completion.json`, alongside the
   `completion.lxmf` packet that already existed.
2. On command, `D` publishes the receipt as a **propagated** message addressed to the
   origin, one relay at a time, and the laboratory waits for the handoff and for
   persistence at the relay before the next. Three copies, one per relay.
3. `D` leaves. The origin comes back as a **new process**, with the same identity, and
   fetches from one relay as any recipient would. On receiving, it checks the LXMF
   signature against the key of the recipient it sent to, keeps the packet in
   `receipts/<id>.lxmf` and emits `receipt_received`.
4. The auditor requires the receipt at the origin to authenticate with `D`'s key, to be
   identical to the expected envelope over the **exact bytes** `D` reconstructed, to be
   identical to `D`'s local `completion.json`, and the sessions of `O` and `D` to be
   **disjoint** by their launch and stop timestamps.

The receipt is 395 bytes packed, against 15,664 bytes per stored part: for the proof,
plain replication at every relay costs almost nothing and needs neither parts nor
parity. DNA for the payload, replication for the proof.

## Scenarios and result

Three scenarios with the required result stated before execution, in the
[final round](../evidence/gateway-v1-return-1789650235930527800/report.json) with
[frozen sources](../evidence/gateway-v1-return-1789650235930527800/sources.json):
verdict `v1_return_scoped_pass` in 346.4 s.

| Scenario | Time | `D` completed | Copies at relays | Origin visited | Proof obtained via | No proof at |
| --- | --- | --- | --- | --- | --- | --- |
| `returned` | 82.5 s | yes | A, B, C | C | **C** | — |
| `proof_pending` | 116.5 s | yes | A, B; C discarded its own | C, then A | **A** | C |
| `never_completed` | 147.3 s | no (fetched only A and B) | none | A, B, C | none | A, B, C |

In all three the origin had **two sessions** and the recipient **one**, without overlap.
In `returned`, a single relay was enough. In `proof_pending`, the first visit came back
empty and was recorded as proof absent at C; the second, at A, brought the receipt —
proof pendency resolved by another carrier, as the plan anticipated. In
`never_completed`, `D` stayed incomplete, published nothing, and the origin visited all
three relays receiving nothing at all: no false proof appeared.

## Evidence and audit

`v1_return_audit.py` recomputes from the packets and the record:

- **Entry** — the three custody receipts from the first half, checked the same way.
- **Local exit** — the G3/G4 audit over `D`'s packets.
- **Exit at the origin** — exactly one `receipts/<id>.lxmf`, authenticated with `D`'s
  key, addressed to the origin, equal to `receipt_envelope(data_envelope(...))` over the
  reconstructed content and equal to `D`'s `completion.json`. If `D` did not complete,
  the existence of any receipt fails the round.
- **Disjunction** — the intervals of `O` and `D` derived from the `launch`/`stop`
  events; any overlap fails; an origin that never returned fails.
- **Route** — which relay delivered the proof and which were visited before without it.

The auditor's tests include what it **must fail**: a receipt forged by another identity;
a receipt over other bytes; a receipt existing without completion; overlapping sessions;
an origin that never came back.

## Rounds and checks

The first real execution failed with `proof via None`, and the reason is a design
finding, not a coding one. The receipt **did reach** the origin, which rejected it:
`receipt from an unknown recipient`. The origin is a new process after the offline
period, and the list of "who I sent to" lived only in memory. Without it, the origin
does not recognise its own proof. The fix persists the recipients in `recipients.json`,
and that becomes part of the declared state the sender has to keep — which is honest to
say: **verifiable delivery requires whoever sends to keep what they expect to receive.**
The next round passed.

The gaps between sessions were short — tenths of a second between one stopping and the
other launching — but strictly disjoint by the timestamps. The claim is logical
disjunction, not long offline periods.

The run through the declared reproduction path repeated the verdict in 342.8 s, with the
same proof routes per scenario: [second round](../evidence/gateway-v1-return-1789650685925011100/report.json).

- Fast V1 tests in the pinned environment: **22 passed, 2 opt-in skipped**.
- `unittest discover -s window/tests` in the pinned environment: **163 passed, 8 opt-in
  skipped**.
- `python -m pytest window/tests probes/tests -q` on the global Python: **167 passed, 19
  skipped**; modules depending on RNS/LXMF run separately in the pinned environment. The
  real G0–G4 runs were not repeated in this delivery.
- `g2_receiver.py` gained one compatible line, to write `completion.json`; the 40 G1/G2
  tests passed.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**, and `probes/` no longer exists: the pre-Dethron work left the tree when the
repository was prepared for publication.

## Limits

Same host, loopback TCP, cooperative relays: no genuinely hostile relay, and the discard
in `proof_pending` is a laboratory command. The replication and return mechanism is
LXMF's propagation; the contribution here is the evidence contract — what the receipt
proves, how it is checked, how proof pendency is reported — and the controls that must
fail.

The proof only arrives if the origin reaches **some** relay still carrying the copy. How
long relays retain copies was not measured; it is propagation node policy and enters as
a declared dependency, not as a guarantee. One round per scenario, one 24 KiB object, no
statistical estimate. The origin only accepts receipts from recipients it registered — a
receipt from an unknown party is rejected, which is desirable, and means
`recipients.json` is part of the state to preserve.

## Reproduction

Use the environment pinned in [G0](G0_REFERENCE.md#reproduction), from the repository
root:

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_v1_*.py'
$env:RUN_GATEWAY_V1_RETURN='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_v1_return_reference.py
Remove-Item Env:RUN_GATEWAY_V1_RETURN
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only v1_return
```

The real campaign takes about six minutes and records each scenario separately. Local
artifacts include laboratory keys and are ignored by Git.

## Decision and next step

With both halves, V1 is within its declared scope: proof of entry by custody,
localizable pendency, proof of exit at the destination, and proof of exit obtained by
the origin without direct contact with the destination, with proof pendency visible when
the visited carrier does not hold it. This is verifiable delivery in a laboratory — it is
not guaranteed delivery, and the document does not call it that.

Next slice: **V2 — reproduction by a stranger**, a clean clone on a second machine, one
command per milestone, the same verdict, with no help from whoever wrote the code.
