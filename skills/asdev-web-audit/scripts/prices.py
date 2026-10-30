"""List prices per model, as dollars per token, for the tools that price transcript usage.

One table for session_cost.py and agent_audit.py (from the work setup, 2026-10-30). Before it, both
priced every model as Opus 5.5, so a Sonnet executor or a Haiku helper looked as dear as Opus.

Sources: the claude-api skill's model table (cached 2026-10-06) and the Claude Haiku 5.5
announcement (2026-10-08), which also cut Claude Sonnet 5.5 cache reads from $0.20 to $0.10.
Cache reads are 0.1x input except where the table says otherwise; cache writes are 1.25x input
(5-minute) and 2x input (1-hour) on every model. Update the table when a price changes.
"""

# model: (input, output, cache read), dollars per million tokens. Claude Mythos 5.1 prices as Fable 5.1.
LIST = {
    "claude-fable-5-1": (10.0, 50.0, 0.25), "claude-mythos-5-1": (10.0, 50.0, 0.25),
    "claude-fable-5": (10.0, 50.0, 1.0), "claude-mythos-5": (10.0, 50.0, 1.0),
    "claude-opus-5-5": (4.0, 20.0, 0.20), "claude-opus-5": (5.0, 25.0, 0.5),
    "claude-opus-4-8": (5.0, 25.0, 0.5), "claude-opus-4-7": (5.0, 25.0, 0.5), "claude-opus-4-6": (5.0, 25.0, 0.5),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10), "claude-sonnet-5": (2.0, 10.0, 0.2), "claude-sonnet-4-6": (3.0, 15.0, 0.3),
    "claude-haiku-5-5": (0.10, 0.50, 0.01), "claude-haiku-4-5": (1.0, 5.0, 0.1),
}
# A request whose input exceeds the threshold is priced entirely at the higher rates.
LONG = {"claude-haiku-5-5": (100_000, (0.50, 2.50, 0.05))}
# An unrecognised id or a bare alias prices as the newest release of its family.
FAMILY = {"fable": "claude-fable-5-1", "mythos": "claude-mythos-5-1", "opus": "claude-opus-5-5",
          "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
DEFAULT = "claude-opus-5-5"


def resolve(model: str | None) -> str:
    """The table key a transcript's model id prices as: the longest key it starts with, else its family."""
    m = (model or "").lower()
    keys = [key for key in LIST if m.startswith(key)]
    if keys:
        return max(keys, key=len)
    return next((key for fam, key in FAMILY.items() if fam in m), DEFAULT)


def rates(model: str | None, context: int = 0) -> dict:
    """Dollars per token for one request: in, w5 (5-minute write), w1h (1-hour write), rd, out.
    `context` is the request's whole input (fresh, cache writes and cache reads)."""
    key = resolve(model)
    inp, out, rd = LIST[key]
    if key in LONG and context > LONG[key][0]:
        inp, out, rd = LONG[key][1]
    return {"in": inp / 1e6, "w5": 1.25 * inp / 1e6, "w1h": 2 * inp / 1e6, "rd": rd / 1e6, "out": out / 1e6}
