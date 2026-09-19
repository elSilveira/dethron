# G0 — a real reference before widening Dethron

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

Date: 15/09/2026. Bound to the [master plan](https://github.com/elSilveira/dethron-research/blob/master/DETHRON_MASTER_PLAN.md).

Continued, 16/09/2026: [G1 integrated and validated](G1_INTEGRATION.md). The next steps
below record the decision taken on concluding G0.

## Frozen requirement

Laboratory use: an origin leaves messages at gateways while the recipient is offline.
The origin departs; the gateways are killed abruptly, keep their disks and restart. The
recipient keeps its identity, visits the gateways at separate moments and receives the
contents intact.

The scope tests a plausible technical need. It is not demand research, a market
benchmark or a demonstration of commercial novelty.

| Parameter | Configuration |
| --- | --- |
| Reference | Reticulum/rns 1.5.4 + LXMF 1.1.1, real packages from PyPI |
| Environment | Windows, Python 3.10.11, one computer |
| Roles | O, A, B, C, D, each instance in its own process and directory |
| Messages | 1,024, 65,536 and 1,048,576 bytes; deterministic SHAKE-256 content |
| Distribution | A holds the small one, B the medium, C the large; whole objects |
| Negative | An extra 1,024-byte message at A, with a recipient identity never started |
| Contacts | O connects to A/B/C; then D connects only to A, then B, then C |
| Transport | TCP on 127.0.0.1; no AutoInterface, no instance sharing, no third-party transport |
| Discovery | The propagation nodes' native announces; contacts and public keys provisioned by the run |
| Persistence | LXMF's native `messagestore`; its algorithm is not replaced |
| Configured limits | Propagation and delivery: 2,048 kB; sync: 8,192 kB (decimal kB in the API); autopeer disabled |
| Protection | Native encryption and signing; the native propagation cost kept |
| Crash | `os._exit(23)`, with no shutdown handlers; directory and disk kept |
| Deadline | 120 s after confirming storage and restarting the propagation nodes; includes D's contacts and restarts |
| Preparation waits | Up to 180 s per transfer; up to 60 s for persistent indexing |

The 120 s deadline **does not include** the initial send nor the restart of the
propagation nodes. The timestamps allow those stages to be measured separately. This is
the G0 scope of whole objects that the plan permits, not the G2 scenario of
complementary fragments. No payload was reduced to fit the reference's default limit:
the public limit was raised before the 1 MiB send.

## Decision criteria

- **Meets the scope:** three correct contents at the destination within the deadline, a
  valid origin signature, the origin shut down, persistence after the crash and no false
  delivery in the negative control.
- **Reproducible gap:** a requirement failure after investigating the configuration and
  reproducing the cause. A harness failure is not an advantage for Dethron.
- **Inconclusive:** an execution error, missing evidence or an unresolved configuration.

The send callback is called `handoff_only` in the evidence: it proves neither delivery
nor completed persistence. The test waits for indexing, restarts the propagation nodes,
and only counts delivery when it reads the received packet at D.

## Audit and controls

`gateway_contract.py` compares the whole content against the expected one and checks the
Ed25519 signature directly with `cryptography`, without trusting LXMF's validation
boolean. The MessagePack parser is the one RNS supplies. The signature is the origin's:
**it is not a receipt signed by the recipient and sent back to the origin**. Here,
delivery is observed by the harness in the receiving process.

`gateway_archive.py` re-reads the artifacts after the processes exit, checks the
sequence, the three packets and the presence of the absent recipient's message in A's
store. A generic message counter, on its own, does not pass that control. The auditor's
tests reject corruption, a swapped endpoint, unexpected content, a "sent" state used as
a receipt, an invalid sequence, and another identity's store used to justify the
negative.

The corruption controls are tests of the **auditor**, not a campaign of attacks injected
into the native transport. The absent recipient has no receiving process: the conclusion
is "no delivery observed in 120 s and the message retained", not an impossibility of
future delivery. No 120 s TTL was configured.

## Reproduction

At the repository root, PowerShell:

```powershell
python -m venv window/.venv-gateway
window/.venv-gateway/Scripts/python.exe -m pip install -r window/requirements-gateway.txt
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_gateway_*.py'
$env:RUN_GATEWAY_G0='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_gateway_reference.py
Remove-Item Env:RUN_GATEWAY_G0
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only gateway
```

An alternative, to watch the progress directly:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_gateway_probe.py
window/.venv-gateway/Scripts/python.exe window/gateway_archive.py window/results/gateway-g0-ID
```

Each execution creates its own directory under `window/results/`, holding a manifest,
the configurations, the installed versions, the hashes of the run's sources, JSONL logs
and stderr per process and generation, a timeline and a report. Inconclusive rounds are
kept. Those directories contain disposable laboratory private keys and are ignored by
Git; they are not the public documentation package. The subset the documents cite is
published under [`evidence/`](../evidence/README.md).

## Limits of the evidence

- One host and loopback: this measures no radio, no Wi-Fi/Bluetooth, no WAN, no limited
  bandwidth, no interference, no mobility and no correlated physical failure.
- The supervisor schedules the contacts; there is no demonstration of autonomous
  discovery, of a swarm independent of it, or of bootstrap without provisioning.
- The origin's directory is renamed to `O.offline`, with no active process. That removes
  the path the run used; it is not hostile isolation by permissions.
- The restart keeps the store and the keys. It does not test loss of disk, power,
  hardware, or of every copy of one piece of information.
- The receiver saves bytes delivered by the API; it does not receive the originals over
  the control channel. The harness holds the answer key for the audit and is part of the
  trusted base.
- There is no electrical measurement, no comparative physical footprint, no 5 %
  guarantee, no token, no remuneration and no performance comparison with Dethron at
  this stage.
- One message per size is functional development evidence, insufficient for estimating
  reliability or latency percentiles.

## Architecture decision and next slice

The reference **met the scope executed**. Adopt **integration with Reticulum/LXMF as the
architecture hypothesis for G1**, keeping the v2 core as an experimental component.
Within this scope there is no justification for recreating discovery, encryption and
whole-message propagation. An advantage of our own remains to be demonstrated.

Next implementation, in order:

1. G1: an adapter contract to send, query pendency and receive; telling observed
   delivery, handoff and final confirmation apart. Test persistence, repetition after a
   crash, queue limits and a recipient receipt where required.
2. G2: manifests and exact authenticated parts over the same transport. Each path must
   hold only part of the message; a sufficient union completes and an insufficient union
   stays incomplete. Test duplicates and corrupted parts.
3. Compare exact parts and replication on the same budget of contacts, bytes and
   storage. Introduce an established erasure code only afterwards.
4. If no useful gain appears, keep integration and application, or close the
   own-protocol hypothesis. Radio, autonomy, energy and incentives follow in G3–G9.

None of those next items is implemented by the G0 run.

## Primary sources

- [LXMF and propagation](https://github.com/markqvist/LXMF).
- [Reticulum interfaces](https://markqvist.github.io/Reticulum/manual/interfaces.html).
- [RNS 1.5.4 package](https://pypi.org/project/rns/1.5.4/).
- [LXMF 1.1.1 package](https://pypi.org/project/lxmf/1.1.1/).

The local results are below; the authors' own results are not our benchmarks.

## Record of the local rounds

| Round (`gateway-g0-…`) | Result | Interpretation |
| --- | --- | --- |
| `1789494902001906700` | Inconclusive | The sandbox blocked `taskkill`; shutting the first process down exceeded the deadline. Fixed to an explicit in-process crash with `os._exit(23)`. |
| `1789494979856066300` | Inconclusive | The harness queried the store right after the handoff, before indexing had finished. Fixed to wait for the persisted state before triggering the crash. |
| `1789495077778687500` | Meets the scope; the later audit passed | Three valid deliveries, the store recovered and the negative retained after 120 s. |
| `1789495309858991400` | Meets the scope; the integration test passed | A repeat with the file audit built into the runner; three valid deliveries and the negative retained. |

In the first functional round, times accumulated from `distribution_complete`: 1 KiB in
**4.407 s**, 64 KiB in **8.844 s** and 1 MiB in **13.391 s**. These are observations from
one round, not averages, percentiles or the speed of a real network.

Artifacts from the first functional round:
[report](../evidence/gateway-g0-1789495077778687500/report.json),
[manifest](../evidence/gateway-g0-1789495077778687500/manifest.json),
[timeline](../evidence/gateway-g0-1789495077778687500/timeline.jsonl).
Both inconclusive attempts remain in `results/`, with cause and traceback.

In the final repeat: **4.421 s / 8.828 s / 13.390 s** respectively. The whole automated
test took **167.085 s**, including preparation, sending and the negative window.
[Final report with audit](../evidence/gateway-g0-1789495309858991400/report.json),
[final manifest](../evidence/gateway-g0-1789495309858991400/manifest.json) and
[final timeline](../evidence/gateway-g0-1789495309858991400/timeline.jsonl).

Implementation checks:

- 8 fast contract and auditor tests passed in the reference environment.
- 1 real integration test passed, running the final round above.
- Existing suite: **124 passed, 3 skipped** with
  `$env:PYTHONPATH='window'; python -m pytest window/tests probes/tests -q`. The skips
  are the two modules requiring RNS/LXMF outside the global Python, plus the slow opt-in
  run; those components were executed separately in the venv.
- New modules and tests are under 200 lines; local links checked.
- Failures were observed before the audit behaviours were implemented and before the
  real run was created. The execution errors are preserved; they were counted neither as
  a success nor as a technical gap in the reference.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**, and `probes/` no longer exists: the pre-Dethron work left the tree when the
repository was prepared for publication.
