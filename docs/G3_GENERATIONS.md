# G3 — generations of nodes and of supervisors

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

16/09/2026. A functional laboratory slice over Reticulum 1.5.4/LXMF 1.1.1. The
[closed G2](G2_PARTS.md) authorised this slice: to test H06, a message crossing complete
generations of nodes, including replacing the supervisor.

## Contract

The object is 24,576 deterministic bytes, split into three exact 8,192-byte parts by the
`exact` scheme already used in G2. The origin `O` distributes one part to each carrier
`A`, `B` and `C` and leaves; the recipient is `D`.

The execution has four phases, each in **a different supervisor process**:

| Phase | What it does | Survives the end of the phase |
| --- | --- | --- |
| `seed` | Provisions the declared credential, distributes the parts, retires the origin | A0, B0, C0 |
| `generation-1` | Brings up empty A1/B1/C1, transfers over the network, retires A0/B0/C0 | A1, B1, C1 |
| `generation-2` | Brings up empty A2/B2/C2, transfers over the network, retires A1/B1/C1 | A2, B2, C2 |
| `deliver` | Fetches from all three contacts and reconstructs, or refuses without the credential | nothing |

The carriers are detached processes that **stay alive when the supervisor ends**; the
command channel is a pair of files per node, so any supervisor generation can take over
the nodes still running. A new node ignores commands from earlier incarnations.

The next supervisor may only resume from three declared sources:

1. `checkpoint-N.json`, validated by `g3_contract.py`, which accepts **public metadata
   only** — version, generation, scenario, public identities of origin and destination,
   the object's manifest, validity, and per carrier the destination, public key,
   propagation node and encrypted inventory. Any extra field, private key or payload
   fails the file.
2. The control files of the nodes **still alive**, which carry pid and port.
3. The recipient's declared persistent credential.

Each retired generation is renamed into `retired/` and every supervisor installs an
audit hook that turns any read under `retired/` into a `PermissionError`. A supervisor
that could still reach a retired generation fails at startup, and each phase records
`guard: true` when it ends. For the `seed` phase this only holds after it retires the
origin itself; the interesting guarantees are those of the later phases, which cannot
read what they retired. A successor without `checkpoint-0.json` refuses rather than
improvising.

## Result

The [final round](../evidence/gateway-g3-1789613422588119200/report.json), with
[frozen sources](../evidence/gateway-g3-1789613422588119200/sources.json), passed both
scenarios and the negative control: verdict `g3_scoped_pass`.

| Scenario | Time | Distinct supervisors | Native transfers | Retired | Result |
| --- | --- | --- | --- | --- | --- |
| `complete` | 229.9 s | 4 | 6 | O, A0–C0, A1–C1 | exactly 24,576 bytes, receipt checked |
| `missing` | 198.9 s | 4 | 6 | O, A0–C0, A1–C1 | An explicit refusal, no exit and no receipt |

In the `complete` scenario the three generations used **nine distinct carrier
identities** and the encrypted inventory stayed **identical across the three
checkpoints**: the same stored bytes crossed two complete fleet replacements. The
recipient gathered the three authenticated parts over three contacts and produced
`sha256 ada077a478903115055d93de132441ac15051b603ec36ca9a66cb74b2572dc17`.

In the `missing` scenario the recipient's declared credential was deleted before
delivery. The node refused to start with `declared credential is absent`; there was no
`output.bin` and no receipt. The service stopped explicitly instead of degrading quietly
or falling back to another source.

The negative continuity control runs a second-generation supervisor in a directory with
no checkpoint: it fails, naming the missing `checkpoint-0.json`.

## Evidence and audit

Every round preserves frozen sources, versions, checkpoints, a `timeline.jsonl` for all
phases, per-phase logs, authenticated packets and a report in `results/gateway-g3-ID`.
The auditor in `g3_audit.py` recomputes the claims from those records, without trusting
the experiment's own report:

- each phase was recorded by a single pid and the four pids are distinct;
- each carrier used a different identity in each generation and every original,
  including the origin, appears as retired;
- the six native transfers carried exactly one message each;
- the three checkpoints change fleet and keep the same inventory;
- the packets kept by the recipient authenticate against the origin's key, sit among the
  declared entries, reconstruct the exact digest, and the local receipt matches the
  expected envelope.

Those events are harness evidence, not independent attestation by the hardware or by a
hostile supervisor.

## Rounds and checks

An earlier round passed both scenarios before the run through the declared reproduction
path failed the audit: one transfer was recorded with `stored = 0` and an inventory of
one file. It was not data loss. The node writes the message to storage before the router
finishes indexing it, so the two views of the same state diverge for a moment. The
transfer loop accepted the inventory alone and could retire the previous generation
inside that window.

The fix waits for both views to agree before declaring the transfer complete; the audit
still requires exactly one message per transfer, now without depending on the instant
the sample was taken. That failed round remains in
`results/gateway-g3-1789612781500495200`. The same pass also reduced the channel's cost:
a node's liveness check opened a subprocess every 50 ms of waiting and now runs every
two seconds.

### What reproduction on another machine found

On 17/09/2026, the first [V2](V2_REPRODUCTION.md) execution on a second machine failed
G3 with `B0->B1: declared data never arrived over the network`, while the other seven
paths reproduced with an identical verdict. The cause was not slowness: the laboratory
announced the successor, waited two seconds, asked for the sync **exactly once** and then
sat still for 180 s. With `autopeer=False` nobody reissues that request, although in real
LXMF peers sync repeatedly; the single attempt was lost and the rest was useless waiting.

Handover and fetch began repeating the request until the deadline, recording how many
attempts were needed — and the repetition **did not fix it**: the second machine failed
again, now with `after 12 attempts in 300 s`. That fix treated a symptom; the cause was
elsewhere, and only surfaced once the diagnosis started collecting the nodes' `stderr`.

### The real cause: a valid result discarded by a logging line

`LXStamper.generate_stamp` computes the stamp and then evaluates
`speed = rounds/duration` only in order to write a debug line. `duration` times the
search alone — `start_time` is taken after the workblock expansion — and at a low cost
that search finishes in tens of microseconds. Whenever `time.time()` does not advance in
that interval, `duration` is 0.0 and a `ZeroDivisionError` throws away a result that was
already correct.

The frequency depends on the machine's clock granularity, which on Windows varies with
whatever else is running: `get_clock_info` reports 15.6 ms, while the step observed on
this machine is 0.36 ms. Measured with the upstream function, cost 1 raised the exception
in **12 of 12** runs and cost 8 in none; on the second machine, all of them raised. Hence
the appearance of a local problem.

Raising `peering_cost` does not solve it: it only shortens the odds — it still failed
once in twelve at cost 12 — and charges real work, about 100 ms at cost 14 and 800 ms at
cost 18 per peering key.

The damage is silent because `LXMPeer` generates the peering key on a secondary thread.
It dies, the key is never set, `peering_key_ready()` stays false, **every** sync is
deferred "since a peering key has not been generated yet", and the handover expires with
nothing in the timeline to explain it. That is why repeating the request did not help:
each repetition hit the same deferral.

The same `traceback` is in **this** machine's artifacts, in rounds that passed: here the
race with the clock tick sometimes resolved in time and the key was generated on the next
attempt. On the other machine, never. The defect belongs to LXMF 1.1.1, not to the
experiment, and remains reported upstream; `dethron_gateway/lxmf_stamp.py` reinstates
LXMF's own computation without the logging division, and `test_lxmf_stamp.py` fails once
upstream fixes it, so the workaround can be removed.

With the workaround, the second machine passed G3 in 663 s, and here the **six transfers
pass on the first attempt** with no node leaving a non-empty `stderr` — before, four of
the six needed a second attempt and several nodes recorded the `traceback`. The wait for
a path stayed, for a reason of its own: a sync requested before a path exists costs 12
minutes of deferral in LXMF, which no G3 deadline would reach. The deadlines, measured
only on fast hardware, were widened too. The round with everything fixed passed in
294.8 s.

- Fast G3 tests in the pinned environment: **9 passed, 1 opt-in skipped**.
- `unittest discover -s window/tests` in the pinned environment: **115 passed, 5 opt-in
  skipped**.
- `python -m pytest window/tests probes/tests -q` on the global Python: **154 passed, 12
  skipped**; modules depending on RNS/LXMF run separately in the pinned environment. The
  real G0–G2 runs were not repeated in this delivery.
- Every G3 source is under 200 lines and the local documentation links were checked. The
  global suite keeps the pre-existing warning about the `pytest_asyncio` fixture scope
  configuration.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**, and `probes/` no longer exists: the pre-Dethron work left the tree when the
repository was prepared for publication.

## Limits

Everything ran on one host, over loopback TCP. "Replacing every node" means replacing
processes, identities and directories on the same machine; there was no change of
hardware, of operator or of failure domain. The supervisor is replaced between phases,
but the phases are launched by a proving process; autonomy without any supervisor was not
demonstrated.

Blocking the retired generations is a Python audit hook inside the successor process. It
proves the successor does not read the retired directories; it is not operating-system
isolation against a hostile supervisor, which could simply not install the hook. Ports
and pids come from the control files of the live nodes: transport metadata, with no
content and no keys.

The recipient's credential is a declared persistent dependency. G3 shows the service
stops explicitly without it, not that recovery without a key exists. This was one 24 KiB
object and one round per scenario, with two fleet replacements; it is not a statistical
estimate, there is no continuous churn, and this slice measures neither traffic nor
storage nor energy. Radio, independence from the internet, commercial demand and tokens
all remain unvalidated.

## Reproduction

Use the environment pinned in [G0](G0_REFERENCE.md#reproduction), from the repository
root:

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_g3_*.py'
$env:RUN_GATEWAY_G3='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_g3_reference.py
Remove-Item Env:RUN_GATEWAY_G3
```

Those lines are PowerShell. In cmd the variable is never set and the real test **skips
itself reporting `OK`**, which is exactly how a second machine once reported a run that
never happened. From any terminal, the runner does the same without environment
variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g3
```

The real campaign takes about seven minutes and records each scenario separately. Local
artifacts include laboratory keys and are ignored by Git.

## Decision and next step

H06 is verified within its declared scope: the message crossed two complete generations
of carriers and four supervisors, without consulting the origin, a snapshot or an
undeclared key, and withdrawing the resource declared indispensable produced an explicit
failure. Nothing here supports autonomy without a supervisor, radio, or any saving.

Next slice: **G4 — logical independence**, cutting the external path, starting cold and
using an alternative bridge, keeping the rule of reviewing before advancing.
