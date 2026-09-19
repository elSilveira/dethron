# V3a — two-machine bench: everything proved except that there are two machines

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

18/09/2026. A functional slice over Reticulum 1.5.4/LXMF 1.1.1, on two distinct Windows
machines on the same local network. The [approved V2](V2_REPRODUCTION.md) supplied the
prerequisite: a second machine with a proved environment.

## What this slice settles

Every milestone from G0 to V1 carries the same caveat: *same host, same operating
system, same file system, same failure domain*. V3a removes it, but only if it solves a
problem the single host was hiding.

On one host the supervisor drove the nodes through files it shared with them. Across
machines that stops being innocent: **whatever carries commands during the window also
carries connectivity**, and an isolation claim made over a live control channel proves
nothing. It is the same class of error as G4's `dark` control, which for a while passed
by accident.

## Contract

Each machine receives, **before** the window, a fixed and hashed schedule, and executes
it from its own disk. It receives nothing else.

| Piece | What it guarantees |
| --- | --- |
| `v3_schedule.py` | Ordered steps, inside the window, with a closed action and arguments. Any edit changes the digest |
| `v3_bench.py` | Identities minted in advance, addresses derived without starting a node: no step discovers anything during the window |
| `v3_agent.py` | Waits for the declared instant, counts on its own monotonic clock, and seals the control directory |
| `v3_executor.py` | Turns a step into a real node action; there is no path by which something outside could ask for what the schedule did not declare |

**No common clock.** A start marker would need a live channel to reach both machines —
exactly what an isolated window cannot have. The plan declares the **instant**; each
agent waits for it on the wall clock, switches to the monotonic one, and records the
time it actually observed. The combined skew between the machines is readable in the
evidence, not assumed.

**Deaf by construction and by check.** The agent never reads a command channel, and on
top of that it fingerprints the control directory at the instant the window opens and
compares when it closes. A run in which somebody steered a machine mid-way **fails**.

## Result

Two Windows machines on the same network, relay and origin on `alpha`, recipient on
`beta`, a 16,384-byte object:

| Measure | alpha | beta |
| --- | --- | --- |
| Steps executed | 8, no failure | 5, no failure |
| Lateness at opening | 0.003 s | 0.011 s |
| Maximum drift | 0.016 s | 0.000 s |
| Control channel | sealed | sealed |

**Skew between the windows: 0.007 s.** Seven milliseconds between two machines with no
live channel between them, from the declared instant alone.

**This round's verdict is `v3a_pass_without_machine_evidence`**, not
`v3a_scoped_pass`. Everything above is proved; the distinction between the machines is
not. See the next section.

The recipient reconstructed the exact 16,384 bytes
(`sha256 9e390712447e77dedddd75386db336f7a07fb8b1cc210eff3fff9c172b15b4e6`), with the
packet authenticated against the origin's key and the local receipt valid — the same
cryptographic audit as the earlier milestones.

## The control that decides whether this is worth anything

Two agents on one host execute these same schedules just as obediently. A V3a claim
that does not establish **distinct machines** is worth no more than G1. So the auditor:

- rejects a loopback relay address outright;
- requires each machine to have reported its host identity;
- requires the names to differ;
- requires the relay address to **belong to the relay machine and to no other**.

That auditor earned its place by failing the author's own single-host rehearsal, before
any real round — and it failed the round above too. The agents did not yet write
`host.json`, so the `report.json` carries `evidenced: false` with the reason written in
it: *distinctness rests on the non-loopback address and on the operator, not on this
evidence*.

In practice, what the round establishes on its own is that **the relay was not on
loopback** (`192.168.68.62`). That the two folders ran on different machines is the
operator's observation, and the operator's observation is precisely what this project
does not accept as proof. Host identity recording is now in `v3_agent.py`; what is
missing is a round that exercises it.

## Rounds and checks

The first attempt on two machines **produced no paired round**, and the reason was a
design defect: the bench folder was not single use. Each new attempt found the previous
one's node directories, the `Daemon` refused to launch into them, and the round died at
step 0 with `node already launched` — an error about a node that said nothing about the
real problem. In the attempt the second machine followed, the relay never came up, and
the recipient spent the window fetching from an address where nobody was. Preparing or
executing in an already-used folder is now refused, with a message naming cause and
remedy.

The second attempt failed on the network, and the diagnosis showed the value of
separating hypotheses: `Initial connection ... could not be established: timed out` on
the recipient, while the relay held the message and waited. The network was Public in
Windows and the port was blocked. The test I had proposed for checking this was badly
formed — it told you to test the port with the bench stopped, when nothing listens on
it — and produced `False` even with a correct firewall. A temporary listener separated
the two in seconds.

- Fast V3 tests in the pinned environment: **21 passed**.
- `unittest discover -s window/tests` in the pinned environment: **207 passed, 8 opt-in
  skipped**. That number was measured on the tree of the time; the suite today holds
  **166**, because the pre-Dethron work left the tree when the repository was prepared
  for publication.
- Every V3a source file is under 200 lines.

## Limits

Two machines, one operating system, one domestic wireless network, one 16 KiB object,
one round. This is not a statistical estimate. Ethernet and Wi-Fi were not compared as
distinct media, and no non-IP link took part: **this is not G6 and says nothing about
physical diversity** — that is the V3c slice, over a serial link, which also comes to
serve as the time base.

The control channel is a folder copied by hand between the machines, declared and
excluded from the window by the seal. The machines share the same network
infrastructure and the same power, so correlated failures remain possible. The auditor
proves nobody steered the machines during the window; it does not prove a hostile
operator could not have prepared the bench in bad faith.

## Evidence

[`evidence/v3a-network-20260918/`](../evidence/v3a-network-20260918/) holds the report,
the hashed plan, and each machine's `evidence.jsonl`.

## Reproduction

To prepare two machines from scratch: [V3_SETUP.md](https://github.com/elSilveira/dethron-research/blob/master/window/V3_SETUP.md), including the network
test that separates a firewall from a bench, and how to read the report.

From the repository root, on both machines, with the environment pinned as in
[G0](G0_REFERENCE.md#reproduction). On the relay machine, find the local address with
`ipconfig` and use a **new** folder for every round:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_bench.py C:\dethron\bench3 <RELAY-IP> 600
```

Copy `C:\dethron\bench3\control` to the other machine, to the same path. Then, on each:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_agent.py C:\dethron\bench3 alpha
window/.venv-gateway/Scripts/python.exe window/run_v3_agent.py C:\dethron\bench3 beta
```

Port 45810 must accept inbound connections on the relay machine. When both finish,
bring the other machine's folder next to the first one and produce the verdict:

```powershell
window/.venv-gateway/Scripts/python.exe window/run_v3_report.py C:\dethron\bench3
```

## Decision and next step

The evidence from G0 to V1 holds on two folders that share neither process nor
directory, with nobody steering them during the window, and the object crossed a real
network between non-loopback addresses. This round, on its own, does not establish that
there are two machines.

**[V3c](V3C_BENCH.md) did establish it**, in a later round that recorded the host
identities: `v3c_scoped_pass`, with processors from different vendors and no address in
common. The single-host caveat leaves G0–V1 on that evidence, not on this one.

Repeating this round until `v3a_scoped_pass` remains possible —
[V3_SETUP.md](https://github.com/elSilveira/dethron-research/blob/master/window/V3_SETUP.md) — but it is no longer necessary: what it would prove is
already proved, over a harder medium.
