# V3c — a medium that carries no IP

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

18/09/2026. A functional slice over Reticulum 1.5.4/LXMF 1.1.1, on two physically
distinct Windows machines joined by a Bluetooth SPP link. [V3a](V3A_BENCH.md) built
the two-machine bench; this one changes the medium between them.

## What this slice settles

Every earlier milestone crossed IP. The master plan bets that the overlay lives
without the internet stack, and that had never been exercised: an independence claim
made over TCP is worth nothing.

The difficulty is not configuring a serial link. It is **proving the object could not
have gone another way**. A recipient holding an IP interface, even an unused one,
destroys the claim — because the interface it never used is still a path it had.

## Contract

The recipient is given a serial interface and **nothing else**:

| Piece | What it guarantees |
| --- | --- |
| `config_text(..., serial={'only': True})` | The recipient's node is born with one interface. Asking for IP contacts as well is refused as a contradiction |
| `v3_audit.medium()` | Reads the configuration the node **wrote to disk**, not the schedule that asked for it, and requires the interface set to equal `['Serial']` |
| `v3_agent.preflight()` | Refuses, at load time, a port this machine does not have — before the wait, not after it |
| `v3_bench.TIMES['serial']` | The relay opens the link first, and nothing is written to it until both ends are on it |

The relay is the only node with transport enabled, because it is the only one sitting
between two media. A relay that cannot forward between them makes the second medium
decoration.

## Result

Verdict `v3c_scoped_pass`, on commit `2a38607`:

| Measure | alpha (`elSilveira`) | beta (`DESKTOP-CURVS8Q`) |
| --- | --- | --- |
| Steps executed | 8, no failure | 6, no failure |
| Lateness at opening | 0.001 s | 0.014 s |
| Maximum drift | 0.016 s | 0.016 s |
| Control channel | sealed | sealed |
| Node's interfaces | loopback listener + serial | **`['Serial']`** |

**Skew between the windows: 0.012 s.** The origin handed 29,921 packed bytes to the
relay at 90 s. The recipient's first fetch, at 240 s, caught the sync in progress; the
second, at 320 s, completed. The relay held one message at 240 s and none at 480 s.

The recipient reconstructed the exact 16,384 bytes
(`sha256 9e390712447e77dedddd75386db336f7a07fb8b1cc210eff3fff9c172b15b4e6`), with the
packet authenticated against the origin's key and the local receipt valid.

## The control that decides whether this is worth anything

That the two machines are distinct: processors from different vendors (AMD Ryzen and
Intel), different names, and **no address in common** — the auditor rejects the run if
the two share even one.

That the medium carries no IP: the auditor opens `beta/D/rns/config` — the file the
node wrote, not the one we asked for — and requires `['Serial']`. Ten controls cover
the refusals, including a recipient that merely *listens* on TCP without ever using it.

**This also retires the single-host caveat** left open by V3a: here
`distinct_machines.evidenced` is true, by name and by disjoint addresses.

## Rounds and checks

The first round failed on both machines and spent eight minutes of window saying so.
The recipient's node died with `OSError 1168`, and the relay wedged right after — and
it wedged instructively: `RNS/Interfaces/SerialInterface.py:131` opens the port with
`write_timeout = None`, so `process_outgoing` blocks forever writing to a link with
nobody on the far end. Two failures, one cause.

My first diagnosis of 1168 was wrong. `Element not found` reads like a port that does
not exist, and both machines have a COM3. What exists is the **asymmetry**: one end
waits and the other dials, and the dialling end cannot open its port while the waiting
end is not holding its own. The manual probes never hit this, because a human runs
`listen` before `send`; the bench opened both at instant zero, which over IP is
harmless — a listening socket exists whether or not anyone connects — and over serial
is a race the recipient loses.

- Link characterized before building on it: 16,384 bytes intact at **128 KiB/s**, with
  the digest checked at both ends.
- `v3_serial_probe.py rns` answers whether Reticulum brings the interface up, in 20
  seconds and on one machine, instead of selling the answer for a whole window.
- Full suite in the pinned environment: **222 passed, 8 opt-in skipped**. That number
  was measured on the tree of the time; the suite today holds **166**, because the
  pre-Dethron work left the tree when the repository was prepared for publication.

This round's report was born not knowing which code produced it: git was refusing the
repository over *dubious ownership* and the `commit` field stored the refusal. Fixed in
both runners, and the report was regenerated from the same evidence.

## Limits

**The link is Bluetooth, and Bluetooth is not independent of Wi-Fi.** They share the
2.4 GHz band and often the same combo chip. This proves the absence of **IP**, not the
absence of **radio** nor of a common failure domain. A USB-TTL pair over copper would
close that gap; it was not done.

Inside alpha, the relay and the origin still talk over loopback TCP. What crosses
between the machines carries no IP; the internal wiring of one of them does.

One round, one operating system, one 16 KiB object, one link. This is not a statistical
estimate, and it **says nothing about H19** — traffic migrating to its own medium under
scale is a different question, which one round over one link does not touch.

Because of RNS's `write_timeout = None`, if the recipient drops mid-window the relay
wedges instead of recording an error. The bench works around it through the ordering of
the steps; the defect belongs upstream and is still there.

## Evidence

[`evidence/v3c-serial-20260918/`](../evidence/v3c-serial-20260918/) holds the report, the
hashed plan, and each machine's `evidence.jsonl` and `host.json`.

## Reproduction

On both machines, with the environment pinned as in [G0](G0_REFERENCE.md#reproduction),
and the link proved before any bench:

```powershell
window/.venv-gateway/Scripts/python.exe window/v3_serial_probe.py list
window/.venv-gateway/Scripts/python.exe window/v3_serial_probe.py rns COM3
```

With a **new** folder, on the relay machine:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_bench.py C:\dethron\v3c2 --serial COM3 COM3 600
```

Copy `C:\dethron\v3c2\control` to the other machine, to the same path, then on each:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_agent.py C:\dethron\v3c2 alpha
window/.venv-gateway/Scripts/python.exe window/run_v3_agent.py C:\dethron\v3c2 beta
```

The recipient sits still for the first 30 seconds by schedule, not by hanging. When
both finish, bring the other machine's folder next to the first one:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_report.py C:\dethron\v3c2
```

## Decision and next step

The V trail is closed as far as it could close on its own. G0 through V1 no longer
carry the single-host caveat, and there is a run in which verifiable delivery crossed a
medium without IP.

What is missing for outside acceptance is no longer physical medium: it is **somebody
outside running V2**. No number of links makes up for nobody without contact with the
author having reproduced the work.
