"""Keep an LXMF defect from discarding a valid stamp.

`LXStamper.generate_stamp` computes the stamp, then evaluates
`speed = rounds/duration` only to write a debug log line. `duration` times the
search alone — `start_time` is taken after the workblock is expanded — and for a
low stamp cost that search finishes in tens of microseconds. Whenever
`time.time()` does not advance across it, `duration` is 0.0 and a
`ZeroDivisionError` throws away a result that was already correct.

How often that happens depends on the machine's clock granularity, which on
Windows varies with what else is running: `get_clock_info('time').resolution`
reports 15.6 ms, while the observed step on the machine of origin is 0.36 ms.
Measured here with upstream's own function, cost 1 raised in 12 of 12 runs and
cost 8 in none; on the second machine every attempt raised. That is why the
failure looked machine-specific.

The damage is silent where it matters: `LXMPeer` generates the peering key in a
daemon thread, so the key is never set, `peering_key_ready()` stays false, every
sync is postponed "since a peering key has not been generated yet", and a
handover times out with nothing in the timeline to explain it.

Raising `peering_cost` is not a fix: it only shortens the odds, still raised once
in twelve runs at cost 12 here, and costs real work — about 100 ms at cost 14 and
800 ms at cost 18 per peering key.

`install()` restores upstream's own computation without the log division. LXMF
stays pinned at 1.1.1 for reproducibility: this is a workaround, not a fork.
Whether a release after 1.1.1 already guards this has not been checked; that is
the first step before reporting it upstream.
"""
from LXMF import LXStamper
from RNS.vendor import platformutils

UPSTREAM = LXStamper.generate_stamp


class _FrozenClock:
    """The real time module, except that time() never advances."""

    def __init__(self, module):
        self._module = module

    def __getattr__(self, name):
        return getattr(self._module, name)

    def time(self):
        return 0.0


def generate_stamp(message_id, stamp_cost, expand_rounds=LXStamper.WORKBLOCK_EXPAND_ROUNDS):
    """Upstream's dispatch and result, minus the division that only feeds a log line."""
    workblock = LXStamper.stamp_workblock(message_id, expand_rounds=expand_rounds)
    if platformutils.is_windows() or platformutils.is_darwin():
        stamp, rounds = LXStamper.job_simple(stamp_cost, workblock, message_id)
    elif platformutils.is_android():
        stamp, rounds = LXStamper.job_android(stamp_cost, workblock, message_id)
    elif LXStamper.USE_WORKER_MANAGER:
        stamp, rounds = LXStamper.job_linux_managed(stamp_cost, workblock, message_id)
    else:
        stamp, rounds = LXStamper.job_linux(stamp_cost, workblock, message_id)
    value = LXStamper.stamp_value(workblock, stamp) if stamp is not None else 0
    return stamp, value


def defect_present():
    """Ask upstream directly: with a clock that does not advance, is the stamp lost?

    Reading the source is not enough — the guarded line still contains the original
    expression, so a text match reports the defect forever. This runs the real
    function against a frozen clock, which is what a sub-tick search observes, and
    costs about three hashes. Anything other than a clean return keeps the
    workaround installed, since the workaround preserves upstream behaviour anyway.
    """
    original = LXStamper.time
    LXStamper.time = _FrozenClock(original)
    try:
        UPSTREAM(bytes(32), 1, expand_rounds=LXStamper.WORKBLOCK_EXPAND_ROUNDS_PEERING)
        return False
    except Exception:
        return True
    finally:
        LXStamper.time = original


def install():
    """Idempotent, and a no-op once upstream guards the division.

    Returns whether the defect is still present, so an artifact records whether the
    workaround was actually in force during that run.
    """
    present = defect_present()
    if present and getattr(LXStamper.generate_stamp, '__module__', None) != __name__:
        LXStamper.generate_stamp = generate_stamp
    return present
