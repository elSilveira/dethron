# V2 — a reproduction guide for a stranger

> **Where to reproduce this.** The bench that produced this run — the laboratories,
> scenarios, schedules and auditors — lives in [dethron-research](https://github.com/elSilveira/dethron-research), not here.
> This repository carries the library, the command line and the artifacts the run
> produced, so the claims can be checked; the research repository is where they can be
> produced again.

This guide is for somebody who **did not write the code** and will reproduce, on
another machine, the results from G0 to V1 using only the cloned repository. If any
step needs help from whoever wrote it, or any file that is not in the clone, that is a
V2 failure — and it is exactly what this milestone exists to find out.

Total time: about **15 minutes of preparation** and **40 minutes of execution** without
intervention. During execution, do not use the machine for anything heavy and do not
let it suspend.

## The single rule

**Nothing from the original machine comes in.** Do not copy `results/`, virtual
environments, keys, or any file from outside. The clone is the only input. If you
already have an old copy of this project on the machine, use a new folder.

## Prerequisites

| Item | Requirement | How to check |
| --- | --- | --- |
| System | Windows 10 or 11 | G4's evidence uses `netstat`; other systems have not been exercised |
| Python | **3.10.x**, on PATH as `python` (it was run with 3.10.11) | `python --version` |
| Git | any recent version | `git --version` |
| Clone path | **short (up to 100 characters) and without spaces, quotes or accents**, for example `C:\dethron` | Windows caps paths at 260 characters and the experiment artifacts add about 150; G4's bridge refuses spaces. The runner measures this and stops before running if the path is long |
| Network | internet only for `pip install`; the experiments use `127.0.0.1` alone | Windows Firewall may ask about `python.exe`: allow it |
| Disk | ~300 MB (virtual environment and artifacts) | — |

Install Python from the official python.org installer, ticking "Add to PATH"; the
Microsoft Store shortcut cannot create the virtual environment.

## Which terminal to use

The commands below work in **both PowerShell and Command Prompt (cmd)**, because none
of them depends on an environment variable: the runner sets what it needs by itself. If
you find a line starting with `$env:` in another document, it only works in PowerShell —
always prefer the runner.

## Step 1 — clone

In the terminal:

```powershell
git clone https://github.com/elSilveira/dethron.git C:\dethron
cd C:\dethron
git log --oneline -1
```

**Expected:** the last line shows the hash and the message of the most recent commit.
Write that hash down: it goes in your report.

## Step 2 — pinned environment

```powershell
python --version
python -m venv window\.venv-gateway
window\.venv-gateway\Scripts\python.exe -m pip install -r window\requirements-gateway.txt
window\.venv-gateway\Scripts\python.exe -c "import importlib.metadata as m; print({n: m.version(n) for n in ('rns','lxmf','cryptography')})"
```

**Expected:**

- `Python 3.10.x`
- `pip` finishes without `ERROR` (warnings about a newer pip are normal)
- the last line prints exactly
  `{'rns': '1.5.4', 'lxmf': '1.1.1', 'cryptography': '50.0.1'}`

Any other version fails the step: do not continue, report it.

## Step 3 — fast suite

```powershell
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --fast-only
```

**Expected:**

```
fast full                   ran=166 skipped=8 PASS
V2 PASS - summary: C:\dethron\window\results\v2-...\summary.json
```

The 8 skipped are the real reproduction tests, which only run in step 4. It takes about
60 seconds. Nothing beyond Python is needed: there is one count, and there were two
while the tree still held work that predates Dethron.

If **a single** test fails, repeat the command once with the machine idle. If it fails
again, that is a failure: report the complete output.

The first line printed, `environment: {...}`, must end with `"problems": []`. If
`PROBLEM: repository path too long` appears, the clone sits on too long a path: move it
to something like `C:\dethron` and start again from step 2. That case was observed on
the origin machine: a clone on a 135-character path passed the fast suite and failed
**all eight** real experiments with `inconclusive`, because Reticulum could not write
into `rns\storage`.

## Step 4 — the eight real reproduction paths

```powershell
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py
```

The command repeats the fast suite and then runs, one at a time, the eight real
experiments. Each brings up genuine Reticulum/LXMF processes on `127.0.0.1`, writes a
directory into `window\results\` and produces a verdict. **Expected**, in order:

| The printed line starts with | Expected verdict | Reference time |
| --- | --- | --- |
| `test_gateway_reference.py` | `meets_scoped_requirement` | 208 s |
| `test_g1_reference.py` | `meets_g1_lab_contract` | 31 s |
| `test_g2_reference.py` | `meets_g2_scoped_contract` | 185 s |
| `test_g2_comparison_reference.py` | `g2_scoped_pass` | 754 s |
| `test_g3_reference.py` | `g3_scoped_pass` | 295 s |
| `test_g4_reference.py` | `g4_scoped_pass` | 167 s |
| `test_v1_reference.py` | `v1_custody_scoped_pass` | 213 s |
| `test_v1_return_reference.py` | `v1_return_scoped_pass` | 332 s |

Every line must end with `PASS` and the last line must be `V2 PASS - summary: ...`.
**No console window should open** during execution; the experiment processes run hidden.
If windows flash, note when and report it — that happened on the origin machine before a
fix and is useful data. The reference times were measured on the origin machine. On an
already validated second machine, the same paths took between 1.0 and 2.3 times those
values — G3, for example, 663 s against 295 s. **Up to three times** indicates no
problem. A path that exceeds three times its reference, or hangs for more than 15
minutes printing nothing, should be interrupted with `Ctrl+C` and reported.

## What must be identical and what may differ

**Identical to what is expected, or it is a failure:**

- the eight verdict strings and the final `V2 PASS`;
- the fast suite counts: 166 and 8;
- inside each `report.json`, the scenario results: which completed, the pendency lists,
  the route of the proof, the presence of the refusal, zero IP endpoints in G4's
  isolated scenarios and at least one in the `ip` baseline.

**May and will differ, with no problem:**

- every time in seconds;
- hashes, identities, `transient_id`, PIDs, ports and directory names under `results/`;
- the exact number of bytes carried and the number of endpoints in G4's `ip` baseline
  (here there were three; any value above zero will do).

The documents under `window/*.md` point at `results/…` directories from the original
machine; those links **do not exist in your clone** until you run step 4, and even then
will carry different names. This is expected and is declared in them.

## Result: approved on 18/09/2026

The complete execution on a second machine, in a single pass, **passed**: verdict
`v2_pass` in 58.0 minutes, with the eight paths producing the declared verdict and the
suite at 113 and 8 — `cargo` was absent and the runner detected that by itself, as it
should.

| Path | Verdict | Time | Reference |
| --- | --- | --- | --- |
| `test_gateway_reference.py` | `meets_scoped_requirement` | 214.8 s | 208 s |
| `test_g1_reference.py` | `meets_g1_lab_contract` | 30.1 s | 31 s |
| `test_g2_reference.py` | `meets_g2_scoped_contract` | 181.0 s | 185 s |
| `test_g2_comparison_reference.py` | `g2_scoped_pass` | 744.6 s | 754 s |
| `test_g3_reference.py` | `g3_scoped_pass` | 704.1 s | 295 s |
| `test_g4_reference.py` | `g4_scoped_pass` | 366.6 s | 167 s |
| `test_v1_reference.py` | `v1_custody_scoped_pass` | 501.9 s | 213 s |
| `test_v1_return_reference.py` | `v1_return_scoped_pass` | 658.6 s | 332 s |

The code executed was commit `1e2d190`, deduced from the suite counts and the
expectations recorded in the summary; the runner **did not record** which commit it ran,
which is a failure of the instrument and not of the result. It records it now, and the
summary fails visibly if `git` does not answer.

### What this result is, and what it is not

It is reproduction on an independent machine, by somebody who did not write the code,
following the document alone. It is not reproduction by a stranger in the strict sense:
whoever ran it is the project's author, had contact with whoever wrote the code and, on
the first attempt, needed an explanation outside the guide — which by this very
criterion was a failure, recorded below. This pass tested the already corrected guide
and needed no help.

## First real execution, 17/09/2026

The first execution of this guide on a second machine **failed**, and what it found is
worth recording, because that is what the milestone exists for:

| What failed | Cause | Where the fix landed |
| --- | --- | --- |
| Two suite tests | `cargo` absent, and the runner demanded a manual `--no-survival` | The runner detects `cargo` by itself |
| G3, `inconclusive` | An LXMF 1.1.1 defect: a valid stamp discarded by `ZeroDivisionError` on a logging line, silently killing the peering key | [G3](G3_GENERATIONS.md) and `dethron_gateway/lxmf_stamp.py` |
| Repeating G3 per the guide | The instruction used PowerShell's `$env:`; in cmd the variable is not set and the test **skips itself reporting `OK`** | `--only <milestone>`, with no environment variable |

The other seven paths reproduced with an identical verdict on the first attempt. After
the fixes, G3 passed on the second machine too, in 663 s. What was missing was the
complete execution in a single pass, to close the milestone.

## Repeating a single milestone

If only one of the eight failed and you want to repeat just that one, without waiting
the 40 minutes:

```
window\.venv-gateway\Scripts\python.exe window\run_v2_reproduction.py --only g3
```

The accepted names are `gateway`, `g1`, `g2`, `g2_comparison`, `g3`, `g4`, `v1` and
`v1_return`. The output is one `PASS` or `FAIL` line and the verdict obtained.

## If something fails

Run, in the same folder:

```powershell
window\.venv-gateway\Scripts\python.exe window\v2_diagnose.py
```

It writes a text file with the environment, the name and traceback of every test that
failed, and the error recorded in the experiment that did not pass. The path appears on
the last line. Send that file: it is usually enough for the diagnosis.

## What to send back

1. The `window\results\v2-...\summary.json` file (the path appears on the last printed
   line). It contains environment, counts, verdicts and times.
2. The complete console output of steps 2, 3 and 4, copied as text.
3. The hash from step 1, `python --version`, the Windows version and the processor.
4. If something failed: what you did, what appeared, and whether you had to ask anybody
   anything — **that is data**, not an embarrassment.

Do not send the `results\gateway-*` directories: they hold disposable laboratory keys
and are not needed; `summary.json` is enough.

## How the result will be judged

| Situation | Judgement |
| --- | --- |
| Everything identical to what is expected, with no outside help | **V2 approved** |
| A file, command or explanation that is not in this guide was needed | V2 failed on documentation; the guide is corrected and the test repeats |
| A verdict different from the expected one | V2 failed; whether it is environment or a real defect is investigated — both are valid results |
| Failure only on the first attempt of the fast suite, success on the repeat | Approved with a note: intermittency recorded for investigation |

None of these results is bad for the project. V2 exists to find the distance between
"it works on the machine of whoever wrote it" and "it works from what is published",
and any distance found is what it measures.
