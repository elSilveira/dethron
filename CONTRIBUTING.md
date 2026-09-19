# Contributing

The most useful thing you can send is a reproduction: what you ran, what you expected,
what happened. A bug that comes with the command that shows it is already half fixed.

## The house rule

**A claim arrives with the control that would have caught it being wrong.** A test that
only proves the happy path is not evidence; it is a decoration. Before adding a behaviour,
add the test that fails when the behaviour is absent, and say in the test's name what it
refuses.

This is why the code is shaped the way it is. The relay attests only to what is really in
its store. The origin accepts an answer only from the key of the relay it asked. A receipt
is kept only when signed by a recipient that node actually sent to. Each of those is a
place where a convenient shortcut would quietly turn a claim into a lie.

## Running the tests

```
python -m venv .venv
.venv/bin/pip install -e .          # .venv\Scripts\pip on Windows
.venv/bin/python -m unittest discover -s tests
```

The end-to-end test starts three real Reticulum instances and binds a port, so it is
opt-in:

```
DETHRON_ROUNDTRIP=1 python -m unittest tests.test_roundtrip
```

It takes about 35 seconds and is the one that proves the project's claim. Run it before
sending anything that touches `node.py`, `handlers.py` or `cli.py`.

## Style

- Every source and test file stays under 200 lines. When one grows past that, it is
  usually two ideas wearing one name.
- Comments and docstrings say *why*, not *what*. The code already says what.
- Code and commit messages in English.
- No new cryptography. Established primitives, or nothing.

## Things that will be turned down

- A performance claim without the measurement and its uncertainty.
- A feature that widens the promise past what the tests can check.
- Vendored copies of Reticulum or LXMF. They are dependencies.

## Reporting something that looks like a defect upstream

If the fault is in Reticulum or LXMF, say so plainly and include the reproduction. A
defect found and reported upstream is a first-class result for this project, not an
inconvenience. One is already recorded in the research repository, with a reproduction
script and a patch.
