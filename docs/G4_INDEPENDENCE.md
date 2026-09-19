# G4 — logical independence from the external path

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

17/09/2026. A functional laboratory slice over Reticulum 1.5.4/LXMF 1.1.1. The
[executed G3](G3_GENERATIONS.md) authorised this slice: cut the external path, start
cold without it, and deliver over an alternative bridge.

## The problem this experiment had to solve

In G0–G3 the laboratory path was loopback TCP. Cutting one TCP interface and using
another TCP interface would prove nothing: it would be the same path under another name.
So here the "external path" is **the IP stack itself**, and the alternative bridge must
not touch it at any point.

The bridge uses Reticulum's native `PipeInterface`: the node exchanges HDLC frames over a
child process's stdin/stdout, and the two children exchange bytes through append-only
files in a directory. No socket takes part in the path.

    node O ──bridge──> files ──bridge──> relay A
    relay A ──bridge──> files ──bridge──> node D

Removing the medium means renaming the channel's directory: the software stays identical
and the bytes delivered during the cut simply do not arrive.

## Contract

The object is 16,384 deterministic bytes, sent as one exact part over the same
authenticated path as G1–G3. The origin `O` submits to relay `A`'s propagation node and
leaves; the recipient `D` fetches later, with the declared persistent credential. Four
scenarios, with the required result stated before execution:

| Scenario | Configuration | Required result |
| --- | --- | --- |
| `ip` | TCP only; the baseline and the evidence's positive control | delivery |
| `bridged` | **no IP interface since boot**, the bridge alone | delivers the exact bytes |
| `dark` | the medium removed for the whole delivery window | **no** delivery; the object stays pending |
| `cut` | the medium removed on the first attempt, restored on the second | delivery after the restoration |

`bridged` is the cold start the plan requires: the node never had an IP path, it is not a
cut applied after it had been working.

## Result

The [final round](../evidence/gateway-g4-1789615587351184200/report.json), with
[frozen sources](../evidence/gateway-g4-1789615587351184200/sources.json), passed all four
scenarios in 166.2 s: verdict `g4_scoped_pass`.

| Scenario | Time | Delivered | IP endpoints observed | Bytes over the bridge | Lost in the cut |
| --- | --- | --- | --- | --- | --- |
| `ip` | 17.5 s | Yes | **3 across 2 processes** | — | — |
| `bridged` | 19.0 s | Yes | **0 across 6 processes** | 32,701 | 0 |
| `dark` | 63.6 s | **No** | 0 across 6 processes | 0 | 53 |
| `cut` | 66.2 s | Yes | 0 across 6 processes | 32,694 | 53 |

In the `dark` scenario the native fetch ended in a failure state, `D` produced neither
output nor receipt, and the relay **went on holding the object**: pendency preserved,
with no false success. In `cut`, the first attempt failed with 53 bytes lost into the
removed medium and the second, after restoring the directory, delivered the exact bytes.

## Why the absence of a hidden path is verifiable

A "zero" is only worth something if the tool that produced it can see a real path. That
is why the `ip` scenario is a mandatory positive control: in it the system's `netstat`
**must** report endpoints, and it reported three. In the isolated scenarios the same
tool, applied to the same kinds of process, reported zero.

The verification covers four independent layers:

1. **Configuration.** The auditor re-reads each node's configuration from the record and
   requires all three to be isolated in the scenarios without IP: `PipeInterface` only,
   and `share_instance = No`. Without that second condition Reticulum itself would open
   the shared instance's port on 127.0.0.1.
2. **Operating system.** TCP/UDP endpoints of the **nodes and of the bridges too**, by
   pid: six processes inspected per isolated scenario, zero endpoints. The bridges count
   because a hidden path could be in them.
3. **Medium.** Each bridge keeps a ledger of what it carried. In the delivering
   scenarios, more bytes than the object crossed the files; in `dark`, zero bytes crossed
   and 53 were lost against the absent medium.
4. **Content.** The packets kept by `D` authenticate against the origin's key, match the
   declared submission, reconstruct the exact digest, and the local receipt matches the
   expected envelope, by the same audit as G1–G3.

The auditor's tests include the cases where it **must fail**: a node that still reaches
IP, an endpoint present in an isolated scenario, an IP baseline with no endpoint at all,
a sample that inspected no process, a cut without loss, and an object that never crossed
the medium.

## Limits

This demonstrates independence from the **IP stack**, not physical independence. Same
host, same operating system, same file system and same failure domain. The file channel
has none of a real medium's loss, latency, range or contention; the only loss measured is
the one the cut caused. Radio and two distinct physical media remain G6, and nothing here
supports a claim of operating without the internet in the field.

The socket evidence is a sample taken during the delivery window, not continuous packet
capture. `netstat` shows the operating system's endpoints; it does not prove the absence
of side channels that use no sockets, and the experiment itself uses one of those, on
purpose. The cut is the removal of a directory, not physical interference. This was one
round per scenario and one 16 KiB object, with no statistical estimate.

## Reproduction

Use the environment pinned in [G0](G0_REFERENCE.md#reproduction), from the repository
root:

```powershell
$env:PYTHONPATH='window'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p 'test_g4_*.py'
$env:RUN_GATEWAY_G4='1'
window/.venv-gateway/Scripts/python.exe -m unittest discover -s window/tests -p test_g4_reference.py
Remove-Item Env:RUN_GATEWAY_G4
```

Those lines are PowerShell. From any terminal, the runner does the same without
environment variables:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g4
```

The real campaign takes about three minutes and records each scenario separately. Local
artifacts include laboratory keys and are ignored by Git.

## Rounds and checks

Three real defects appeared before the result and are fixed, each with a test:

- The bridge command was quoted. `configobj` strips the outer quotes and `shlex` joined
  everything into a single argument, so the node did not even start. The contract now
  builds and validates the command, refusing a path with a space or a quote.
- Building the recipient's configuration **recreated the channel's directory**, which
  undid the cut and made the `dark` scenario deliver. Creating the medium became an
  explicit act, and restoring a medium that reappeared on its own is now an error.
- A node shut down immediately does not reap the bridge Reticulum created, and the
  bridges were left orphaned. The laboratory and the probe now reap them.

The run through the declared reproduction path repeated the result in 167.0 s, with the
same verdicts per scenario and the same endpoint counts:
[second round](../evidence/gateway-g4-1789615826730038800/report.json).

- Fast G4 tests in the pinned environment: **24 passed, 1 opt-in skipped**.
- `unittest discover -s window/tests` in the pinned environment: **139 passed, 6 opt-in
  skipped**.
- `python -m pytest window/tests probes/tests -q` on the global Python: **167 passed, 14
  skipped**; modules depending on RNS/LXMF run separately in the pinned environment. The
  real G0–G3 runs were not repeated in this delivery.
- Every G4 source is under 200 lines and the local documentation links were checked. The
  global suite keeps the pre-existing warning about the `pytest_asyncio` fixture scope
  configuration.

Those counts were measured on the tree of the time. The suite today holds **166 passed,
8 skipped**, and `probes/` no longer exists: the pre-Dethron work left the tree when the
repository was prepared for publication.

## Decision and next step

Delivery within the declared scope does not depend on the IP stack, and removing every
bridge prevents delivery while preserving pendency, as the plan required. This does not
authorise claiming physical autonomy or operation over radio.

Next slice: **G5 — survival**, with a 5 % campaign under chosen, random, correlated and
targeted loss distributions, scored separately per failure model.
