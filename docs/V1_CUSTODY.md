# V1 — custody: proof of entry and localizable pendency

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

17/09/2026. The first half of milestone V1 of [version 7 of the plan](https://github.com/elSilveira/dethron-research/blob/master/DETHRON_MASTER_PLAN.md),
over Reticulum 1.5.4/LXMF 1.1.1. The second half — the recipient's receipt returning to
the origin through the relays — is in [V1_RECEIPT_RETURN.md](V1_RECEIPT_RETURN.md).

## What is proved here, and what is not

Up to G4, the only evidence that an object had been entrusted to the network was LXMF's
`handoff` callback in the origin's process: a harness event, unsigned, unpersisted and
without evidential value. This slice replaces it with a **custody receipt signed by the
relay**, obtained by the origin while still in contact, and with an auditor that derives
pendency from those receipts.

Custody is **the relay's claim**. It proves the object entered the network; it does not
prove exit. Only the recipient's receipt proves exit, and it is still produced locally
on `D`, as in G1–G4. The auditor keeps the two proofs separate by construction: a
`handoff` without a custody packet is recorded as an absence, and custody never changes
the `completed` state.

## LXMF facts confirmed in the installed source

Every item below was read in the package's code, not deduced:

- `LXMessage.pack()` sets `transient_id = SHA-256(lxmf_data)` for propagated messages
  (LXMessage.py, line 434), so **the origin knows the id** in the handoff callback.
- The relay recomputes the same id over the bytes it received (LXMRouter.py, line 2495)
  and stores `[destination, path, received, size, …]` by id.
- The file on disk is `lxmf_data + stamp`, so **the file's sha256 is not the
  `transient_id`**. The link between origin and relay is by id; the file digest is a
  second binding, checked against the inventory the relay reported.
- `full_hash` is SHA-256 (Identity.py, line 352); DIRECT delivery exists and is the
  default method; the delivery callback receives an `LXMessage` carrying `packed` and
  `source_hash` (LXMRouter.py, line 1914).

## Contract

Three new envelopes in `dethron_gateway/protocol.py`, with closed field sets and
bounds, leaving `data` and `receipt` untouched:

| Envelope | Who signs | Content |
| --- | --- | --- |
| `custody_request` | origin → relay | `transient_id`, the origin's public key |
| `custody` | relay → origin | `transient_id`, the recipient as the relay sees it, the size and digest of what is on disk, the instant of reception |
| `custody_refusal` | relay → origin | `transient_id` and a readable reason; an absence of custody is never a silence |

The relay only attests what it finds in `propagation_entries`, waiting up to 10 s for
asynchronous indexing; beyond that, it refuses. The origin only accepts the answer
coming from the key of the relay it asked, for exactly the `transient_id` requested, and
keeps the raw LXMF packet in `custody/<id>.lxmf`. The relay keeps a copy of what it
issued in `custody/<id>.issued.json`.

Four scenarios, with the required result stated before execution:

| Scenario | What happens | Required result |
| --- | --- | --- |
| `delivered` | three parts, custody from each relay, `D` fetches from all three | 3 proofs of entry, proof of exit |
| `pending` | the same, `D` never appears | 3 proofs of entry, no exit, pendency at A, B and C |
| `discarded` | relay B attests and then discards the part | 3 proofs of entry, no exit, **B named** as having attested and not delivered |
| `fake` | the origin asks for custody of an id never submitted | a signed refusal, no attestation for that id |

## Result

The [final round](../evidence/gateway-v1-1789648766782072700/report.json), with
[frozen sources](../evidence/gateway-v1-1789648766782072700/sources.json), passed all four
scenarios in 211.6 s: verdict `v1_custody_scoped_pass`.

| Scenario | Time | Proofs of entry | Exit | Derived pendency | Refusal |
| --- | --- | --- | --- | --- | --- |
| `delivered` | 55.3 s | 3 | exactly 24,576 bytes, valid receipt | none | — |
| `pending` | 43.2 s | 3 | no | `awaiting_contact: A, B, C` | — |
| `discarded` | 51.6 s | 3 | no; parts 0 and 2 | `attested_not_delivered: B` | — |
| `fake` | 61.5 s | 3 | exactly 24,576 bytes | none | `transient id not in store` |

The object is 24,576 bytes in three exact parts of 8,192; each relay stored 15,664 bytes
per part, including envelope, encoding and stamp, and every attestation declared that
same size. Pendency tells apart two situations other systems conflate: in `pending`
nobody fetched, so the relays are **awaiting contact**; in `discarded` `D` fetched from
all three and B had nothing, so B is **named**. The distinction comes from the fetch
events, not from an opinion.

## Evidence and audit

`v1_audit.py` recomputes everything from the packets and the record:

- **Entry**: for each `handoff`, it requires `custody/<id>.lxmf` at the origin, checks
  the LXMF signature against the relay's public key, the declared recipient and the
  `transient_id`, and confirms that the attested digest appears in the inventory the
  relay reported right after the handoff. A handoff without a packet is `missing_entry`.
- **Exit**: the same audit as G3/G4 — packets from `D` authenticated against the
  origin's key, parts validated, byte-for-byte reconstruction and a local receipt.
- **Pendency**: per relay holding custody whose part did not arrive, `awaiting_contact`
  if nobody fetched from it, `attested_not_delivered` if they did and nothing came.
- **Refusal**: checked against the relay's key; the existence of an attestation for the
  fake id would fail the round.

The auditor's tests include the cases where it **must fail**: a handoff without custody
is not proof of entry; custody for another id or another recipient is rejected; a digest
that does not match the relay's inventory is rejected; custody never implies delivery; a
relay without custody is not blamed for a missing part.

## Rounds and checks

The first real execution failed the audit with `handoff without custody: ['C']`, and the
reason is instructive. The `custody` command's *ack* is an event sharing the name of the
attestation and also carrying the `transient_id`; the scenario confused one with the
other, recorded custody from C that did not exist, and retired the origin before C
answered — the third request was still queued. **The scenario lied and the auditor
refused**, because it trusts only the signed packet on disk. The events became
`custody_received` and `custody_refused`, distinct from the command, and the next round
passed with C attesting normally.

The run through the declared reproduction path repeated the verdict in 209.0 s, with the
same per-scenario results: [second round](../evidence/gateway-v1-1789649067110742100/report.json).

- Fast V1 tests in the pinned environment: **13 passed, 1 opt-in skipped**.
- `unittest discover -s window/tests` in the pinned environment: **153 passed, 7 opt-in
  skipped**.
- `python -m pytest window/tests probes/tests -q` on the global Python: **167 passed, 17
  skipped**; modules depending on RNS/LXMF run separately in the pinned environment.
  The real G0–G4 runs were not repeated in this delivery.
- V1 sources under 200 lines; `protocol.py` was extended without changing the `data` and
  `receipt` envelopes, and the 40 G1/G2 tests that consume it passed.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**, and `probes/` no longer exists: the pre-Dethron work left the tree when the
repository was prepared for publication.

## Limits

Same host, loopback TCP: the medium is not the question here, the evidence is. Custody
is a claim: a hostile relay can sign and discard, and that is exactly what `discarded`
simulates — by a laboratory command, not by a genuinely hostile relay. What the audit
guarantees is that such conduct **gets named** when the recipient fetches and receives
nothing; it does not prevent it.

The origin has to be in contact with the relay to obtain custody. That holds for entry,
which is local by nature; it does not hold for exit. In this delivery the recipient's
receipt still had no way back to an offline origin; the second half of V1 and hypothesis
H20 were executed next, in [V1_RECEIPT_RETURN.md](V1_RECEIPT_RETURN.md). This was one
round per scenario and one 24 KiB object, with no statistical estimate.

## Reproduction

Use the environment pinned in [G0](G0_REFERENCE.md#reproduction), from the repository
root:

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_v1_*.py'
$env:RUN_GATEWAY_V1='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_v1_reference.py
Remove-Item Env:RUN_GATEWAY_V1
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only v1
```

The real campaign takes about four minutes and records each scenario separately. Local
artifacts include laboratory keys and are ignored by Git.

## Decision and next step

Proof of entry and localizable pendency are within the declared scope. On their own they
are not complete verifiable delivery: what is missing is the recipient's receipt
reaching whoever sent the message, without direct contact with the destination. That
second half — a receipt replicated across the relays, obtained by the origin from any
one of them, with origin and destination never online at the same time — is in
[V1_RECEIPT_RETURN.md](V1_RECEIPT_RETURN.md).
