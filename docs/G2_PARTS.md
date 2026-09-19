# G2 — composing parts across incomplete contacts

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

16/09/2026. A functional laboratory slice over Reticulum 1.5.4/LXMF 1.1.1. G1 justified
this small experiment; it did not approve a network of our own. Two parts: the initial
slice of exact parts, and the widened paired comparison that closes G2.

## Contract and comparison

The profile fixed in `g2_scenario.py` uses 98,304 deterministic bytes, three propagation
nodes A/B/C and one recipient D. Each propagation node receives either a whole object or
one exact 32,768-byte part. The origin leaves and its directory is renamed; the
propagation nodes crash and restart with persistent storage. D visits C, A and B, with a
restart between contacts and a native 64 kB fetch per contact. The contact campaign's
deadline is 120 seconds, excluding distribution.

The three variants use the same calendar and the same native limit:

- `whole`: three complete replicas; they do not fit the per-transfer limit.
- `split`: parts 2, 0 and 1; the union allows exact reconstruction at the third contact.
- `missing`: parts 2, 0 and 0; duplicating one part does not replace the absent part 1.

After the restricted measurement, `whole` receives a 256 kB fetch as a positive control.
That control does not enter the restricted phase's traffic counter. The limit is an LXMF
transfer limit, not a simulation of radio loss and not an identical budget of total
traffic. Part placement is provisioned.

## Evidence and audit

Every attempt preserves the profile, the versions, the source hashes, the manifest, the
events, the authenticated packets, the databases and the report in
`results/gateway-g2-ID`. The auditor checks the origin's signature, the declared
submissions, unique parts, byte-for-byte reconstruction and the signature of the
recipient's local receipt. It also checks completion states and per-contact counts,
including the negative control. Those events are harness evidence, not independent
attestation by the hardware or by a hostile supervisor.

The receipt is produced locally; it does not return to the offline origin. Composing that
return remains pending. Metadata and base64 encoding are included in the LXMF bytes
submitted; the propagation nodes' files and the interface counters are measured
separately. The counters are samples taken before shutdown, not exhaustive packet
capture. The recipient's database, RAM, CPU and energy are not counted as total cost. Do
not infer any general saving from these numbers.

## Reproduction

Use the environment pinned in [G0](G0_REFERENCE.md#reproduction), from the repository
root:

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_g2_*.py'
$env:RUN_GATEWAY_G2='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_g2_reference.py
Remove-Item Env:RUN_GATEWAY_G2
$env:RUN_GATEWAY_G2_COMPARE='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_g2_comparison_reference.py
Remove-Item Env:RUN_GATEWAY_G2_COMPARE
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g2
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g2_comparison
```

The widened campaign takes about ten minutes and records each case separately.

To follow the events, run `window/run_g2_probe.py` with the same Python. Local artifacts
include laboratory keys and are ignored by Git.

## Rounds and checks

The [initial round](../evidence/gateway-g2-1789584864583714400/report.json) passed all three
cases and was re-audited after the auditor was hardened. Two new tests failed before the
fix: an early completion declared in the timeline, and an incorrect count of unique
parts. Both passed after the fix.

The [final round](../evidence/gateway-g2-1789606473945592000/report.json), with
[frozen sources](../evidence/gateway-g2-1789606473945592000/sources.json), passed the real
integration in **229.390 s**, including preparation of the three variants.

| Variant | Completed under the limit | Contacts (s) | LXMF bytes submitted | Bytes at the propagation nodes | TX sampled |
| --- | --- | --- | --- | --- | --- |
| Whole object | No; the 256 kB control completed | 11.360 | 394,437 | 394,800 | 407,931 |
| Three parts | Yes, SHA-256 and receipt checked | 11.546 | 177,723 | 178,080 | 370,252 |
| Missing part | No; two unique parts | 11.563 | 177,723 | 178,080 | 370,658 |

TX includes preparation and distribution plus contacts, up to the sample taken before
the relaxed control. The table's times cover contacts only. These are two development
rounds in a fixed order, not a statistical estimate of reliability.

- Fast G2 tests in the pinned environment: **11 passed, 1 opt-in skipped**.
- `unittest discover -s window/tests` in the pinned environment: **94 passed, 3 opt-in
  skipped** (97 discovered).
- `python -m pytest window/tests probes/tests -q` on the global Python: **142 passed, 9
  skipped**; modules depending on RNS/LXMF run separately in the pinned environment. The
  real G0/G1 runs were not repeated in this delivery.
- Changed sources and tests are under 200 lines; local documentation links were checked.
  The global suite emits a pre-existing warning about the `pytest_asyncio` fixture scope
  configuration.

Those counts belong to the G2 delivery and keep its date and scope. The suite today
holds **166 passed, 8 skipped**, and `probes/` no longer exists: the pre-Dethron work
left the tree when the repository was prepared for publication.

## The widened comparison

The [paired campaign](../evidence/g2-comparison-1789608585567685600/report.json), fixed in
`g2_compare_contract.py`, ran **12 real cases** in 590.984 s: two repetitions, two
scenarios and three policies, with the policy order reversed in the second repetition
and the contact route rotated. The object is 49,152 bytes. `whole` sends the complete
object, `split` sends three exact parts and `xor2` sends two data parts plus one XOR
parity, recoverable from any two.

- Scenario `all`: three contacts (CAB and BAC), native 256 kB fetch per contact.
- Scenario `loss`: one route lost, two contacts (CA and BC), 64 kB fetch.

The budgets declared before execution — 2,000,000 bytes of sampled TX and 8,000,000
bytes of files — were respected in every case; exceeding them would invalidate the case
rather than count as success. Averages over the two repetitions:

| Scenario | Policy | Completed | LXMF bytes | TX sampled | Files (peak) | Contacts (s) |
| --- | --- | --- | --- | --- | --- | --- |
| Three contacts | Whole object | Yes (2/2) | 197,829 | 411,817 | 255,660 | 10.79 |
| Three contacts | Exact parts | Yes (2/2) | 90,351 | 194,079 | 365,384 | 10.75 |
| Three contacts | XOR parity | Yes (2/2) | 134,019 | 282,271 | 474,583 | 10.76 |
| Route lost | Whole object | **No** (0/2) | 197,829 | 207,997 | 205,503 | 7.14 |
| Route lost | Exact parts | **No** (0/2) | 90,351 | 161,493 | 212,934 | 7.16 |
| Route lost | XOR parity | **Yes** (2/2) | 134,019 | 235,173 | 404,567 | 7.17 |

Sampled TX adds distribution and contacts together. Encoding costs 2.7 ms, 1.8 ms and
4.0 ms per object, negligible against the transport. The two repetitions agree case by
case on completion and on traffic within 0.4 %.

## What the widened comparison shows

This is the slice that tests H05, redundant encoding, and the result is a trade-off, not
a general advantage:

- **Without loss, redundancy only costs.** Exact parts complete with the lowest total
  traffic; XOR parity spends **+45 % TX** and **+30 % files** to deliver the same object.
  The whole object spends more than twice the traffic of exact parts and does not fit the
  64 kB per-fetch limit.
- **With one route lost, only redundancy delivers.** With two contacts, XOR parity
  reconstructs the exact bytes; exact parts and the whole object stay correctly
  incomplete. No policy produced a false completion.
- **Storage moves opposite to traffic.** The whole object has the lowest file peak and
  the highest traffic; XOR parity the reverse. There is no dominant policy under this
  contract.

The conclusion it sustains is narrow: under this native transfer limit, the choice
between exact parts and a redundant code is a measurable trade-off between traffic,
storage and tolerance to one lost route. It is not novel against systems that already
fragment and encode messages, and it is not evidence of any general saving.

## Limits of the widened campaign

Two paired repetitions are not a statistical estimate of reliability. Everything ran on
one host, over loopback TCP, with provisioned part placement and loss induced by omitting
a contact, not by radio or congestion. The interface counters are samples taken before
shutdown, not exhaustive packet capture. The recipient's database, RAM, CPU and energy
remain outside the total cost. A single redundant scheme was measured — XOR parity over
three parts — and not an established code such as Reed-Solomon or fountain codes. Repair
after loss was not measured: no policy attempted to recover the lost route. The receipt
is still produced locally and does not return to the offline origin.

## Decision and next step

G2 is closed within its declared scope. H04 was verified in the first slice and H05
receives a conditional result: redundancy improves delivery under route loss and worsens
cost without loss. The hypothesis of a general cost advantage is **refuted** under this
contract and must stop being asserted.

Next slice: **G3 — generations**, replacing every original node and the supervisor while
keeping the service running without consulting a hidden source, with an explicit failure
when a resource declared indispensable is withdrawn. Radio, commercial demand, autonomy
without a supervisor and tokens all remain unvalidated.
