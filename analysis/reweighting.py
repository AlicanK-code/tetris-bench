"""Term-level replay of the project's two contrasting reweightings.

The designs and the arithmetic live in :mod:`tetris_bench.reweighting`, which is
unit-tested; this file is the two experiments and their presentation. Read that
module's docstring for why each function is its own baseline.

Every variant it replays is written to ``runs/published/reweighting/`` so the
numbers below can be checked against source a reader can diff against the
model's original.

    uv run python analysis/reweighting.py
    uv run python analysis/reweighting.py --out /tmp/variants
"""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path

from tetris_bench.engine.game import Game
from tetris_bench.reweighting import (
    Factorial,
    TieCountingAgent,
    ablation_weights,
    render,
)
from tetris_bench.runner import play_game
from tetris_bench.sandbox import SandboxLimits, ScoringSandbox

EVAL_SEEDS = tuple(range(1000, 1010))
PUBLISHED = Path("runs/published/reweighting")

# ---------------------------------------------------------------------------
# qwen3-30b chain 1. Both endpoints share a holes block and a weighted return;
# they differ in how column heights are computed and in the four weights, so the
# two are crossed. The blocks below are verbatim from the saved functions.
# ---------------------------------------------------------------------------

HOLES = """    lines = placement["lines_cleared"]
    holes = 0
    for col in range(10):
        filled = False
        for row in range(20):
            if board[row][col]:
                filled = True
            elif filled:
                holes += 1
"""

#: Iteration 0, verbatim. Scans UP from row 19 and stops at the first filled
#: cell, so a column resting on the floor gives 19 - 19 = 0. Every height is 0,
#: so `max_height` and `bumpiness` are both dead. The probes called this
#: `height: blind`.
DEAD_HEIGHTS = """    heights = []
    for col in range(10):
        lowest_filled = -1
        for row in range(19, -1, -1):
            if board[row][col]:
                lowest_filled = row
                break
        if lowest_filled == -1:
            lowest_filled = 19
        heights.append(19 - lowest_filled)
"""

#: Iteration 5, verbatim. Scans DOWN from row 0, which is the real height.
LIVE_HEIGHTS = """    heights = []
    for col in range(10):
        top_filled = -1
        for row in range(20):
            if board[row][col]:
                top_filled = row
                break
        height = 20 - top_filled if top_filled != -1 else 0
        heights.append(height)
"""

TAIL = """    max_height = max(heights)
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i+1])
"""

#: Iteration 0 carried this and iteration 5 did not. Nominally a tie-breaker
#: worth at most 0.199 -- `row` is the row index, so it prefers lower
#: placements. It is measured as a third factor because a function whose other
#: terms are dead is flat across most candidates, and a tie-breaker on a flat
#: function is not a tie-breaker, it is the policy.
TIE_BREAK = '    unique_term = (placement["row"] * 10 + placement["column"]) * 0.001\n'

WEIGHTS_30B = {
    "old": (100.0, 20.0, 5.0, 1.0),  # iteration 0
    "new": (10.0, 350.0, 15.0, 35.0),  # iteration 5
}
RETURN_30B = "    return lines * %g - holes * %g - max_height * %g - bumpiness * %g"


def build_30b(heights: str, weights: tuple[float, ...], tie: bool) -> str:
    source = "def score(board, placement):\n" + HOLES + heights + TAIL
    if tie:
        source += TIE_BREAK
    source += render(RETURN_30B, weights)
    return source + (" + unique_term\n" if tie else "\n")


# ---------------------------------------------------------------------------
# qwen3-8b chain 3. Here only the weights changed: both endpoints compute their
# terms identically, and iteration 5's extra `bottom_empty` term is omitted
# because it counts all-empty rows upward from row 19 and stops at the first
# non-empty one, which is 0 on any board resting on the floor.
# ---------------------------------------------------------------------------

BODY_8B = """def score(board, placement):
    holes = 0
    heights = []
    max_h = 0
    for c in range(10):
        filled_above = 0
        count = 0
        for r in range(20):
            if board[r][c]:
                filled_above += 1
                count += 1
            else:
                if filled_above > 0:
                    holes += 1
        max_h = max(max_h, count)
        heights.append(count)
    avg = sum(heights) / len(heights)
    unevenness = sum(abs(h - avg) for h in heights)
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * %g - holes * %g - max_h * %g - unevenness * %g
"""

TERMS_8B = ("lines", "holes", "max_h", "unevenness")
WEIGHTS_8B = {
    "it0": (100.0, 1.0, 0.5, 0.1),
    "it5": (50.0, 100.0, 150.0, 150.0),
}


def replay(source: str, seeds: tuple[int, ...]) -> tuple[float, int, float]:
    """Points per piece, pieces placed, and the share of moves tied at the top.

    The tie share rather than ``StrategyDiagnostics.flat_moves``: a tie-breaker
    only ever decides among the candidates that share the maximum, and a
    function can separate its candidates well overall while leaving a large set
    tied at the top. On the 30B's broken function those differ five-fold.
    """
    score = pieces = 0
    with ScoringSandbox(source, limits=SandboxLimits()) as box:
        agent = TieCountingAgent(box)
        for seed in seeds:
            result = play_game(Game(seed=seed, max_pieces=2000), agent)
            score += result.score
            pieces += result.pieces_placed
    return score / pieces if pieces else 0.0, pieces, agent.ties.tied_share


def save(out: Path, name: str, source: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.py").write_text(source)


def run_30b(out: Path, seeds: tuple[int, ...]) -> None:
    print("=" * 78)
    print("qwen3-30b chain 1: a repair and a reweighting in the same step")
    print("=" * 78)
    print("The revision changed three things at once. Crossing all three:\n")
    header = (
        f"  {'heights':<8} {'weights':<8} {'tie-break':<10}"
        f" {'pts/piece':>10} {'pieces':>8} {'tied':>7}"
    )
    print(header)

    cells: dict[tuple[str, str, bool], float] = {}
    for heights, weights, tie in itertools.product(("dead", "live"), ("old", "new"), (True, False)):
        source = build_30b(
            DEAD_HEIGHTS if heights == "dead" else LIVE_HEIGHTS, WEIGHTS_30B[weights], tie
        )
        name = f"30b-chain1-{heights}-{weights}-{'tie' if tie else 'notie'}"
        save(out, name, source)
        rate, pieces, tied = replay(source, seeds)
        cells[(heights, weights, tie)] = rate
        note = ""
        if (heights, weights, tie) == ("dead", "old", True):
            note = "  <- iteration 0"
        elif (heights, weights, tie) == ("live", "new", False):
            note = "  <- iteration 5"
        share = f"{100 * tied:.0f}%"
        print(
            f"  {heights:<8} {weights:<8} {'yes' if tie else 'no':<10} "
            f"{rate:>10.2f} {pieces:>8} {share:>7}{note}"
        )

    print("\nThe revision as the model made it: 41.55 -> 50.19, +8.64.")
    print("Holding the tie-breaker present, so iteration 0 is the real baseline:")
    repair_only = Factorial(
        low_low=cells[("dead", "old", True)],
        high_low=cells[("live", "old", True)],
        low_high=cells[("dead", "new", True)],
        high_high=cells[("live", "new", True)],
    )
    print(f"  repair alone (weights unchanged)   : {repair_only.effect_a:+.2f}")
    print(f"  reweighting alone (heights dead)   : {repair_only.effect_b:+.2f}")
    print(f"  both                               : {repair_only.total:+.2f}")
    print(f"  interaction                        : {repair_only.interaction:+.2f}")
    print("\nAnd on a repaired function, where the terms can actually discriminate:")
    print(
        f"  reweighting alone (heights live)   : "
        f"{cells[('live', 'new', True)] - cells[('live', 'old', True)]:+.2f}"
    )
    print(
        f"  tie-breaker, heights dead          : "
        f"{cells[('dead', 'old', True)] - cells[('dead', 'old', False)]:+.2f}"
    )
    print(
        f"  tie-breaker, heights live          : "
        f"{cells[('live', 'old', True)] - cells[('live', 'old', False)]:+.2f}"
    )


def run_8b(out: Path, seeds: tuple[int, ...]) -> None:
    print("\n" + "=" * 78)
    print("qwen3-8b chain 3: only the weights changed, so which one collapsed it?")
    print("=" * 78)

    for frm, to in (("it0", "it5"), ("it5", "it0")):
        baseline_weights = WEIGHTS_8B[frm]
        target = WEIGHTS_8B[to]
        variants = ablation_weights(baseline_weights, target)
        print(f"\nFrom {frm} {baseline_weights}, moving one weight to its {to} value:\n")
        baseline = 0.0
        for index, weights in variants:
            source = render(BODY_8B, weights)
            label = "baseline" if index is None else TERMS_8B[int(index)]
            save(out, f"8b-chain3-from-{frm}-{label}", source)
            rate, _, _ = replay(source, seeds)
            if index is None:
                baseline = rate
                print(f"  {'(' + frm + ' itself)':<14} {rate:>8.2f} pts/piece")
                continue
            moved = f"{weights[int(index)]:g}"
            print(f"  {label:<14} {rate:>8.2f} pts/piece  ({rate - baseline:+7.2f})   -> {moved}")


#: Four tie-breakers over the same broken function. `placement["row"]` is the
#: top row of the piece's bounding box and row 0 is the top, so a larger row is
#: a lower placement -- which makes the as-written term an accidental "place it
#: low" heuristic. Negating it and dropping the row separate the direction from
#: the mere act of breaking a tie.
TIE_VARIANTS = (
    ("none", "none", ""),
    (
        "as-written",
        "row*10+column (as written)",
        ' + (placement["row"] * 10 + placement["column"]) * 0.001',
    ),
    ("row-low", "row only, prefers low", ' + placement["row"] * 0.001'),
    ("row-high", "row only, negated (prefers high)", ' - placement["row"] * 0.001'),
    ("column-only", "column only, no height information", ' + placement["column"] * 0.001'),
)


def run_tiebreak(out: Path, seeds: tuple[int, ...]) -> None:
    print("\n" + "=" * 78)
    print("Was the tie-breaker worth 26 points for breaking ties, or for its direction?")
    print("=" * 78)
    print("All five share iteration 0's broken function; only the trailing term differs.\n")
    for name, label, tail in TIE_VARIANTS:
        source = (
            "def score(board, placement):\n"
            + HOLES
            + DEAD_HEIGHTS
            + TAIL
            + render(RETURN_30B, WEIGHTS_30B["old"])
            + tail
            + "\n"
        )
        save(out, f"30b-chain1-tiebreak-{name}", source)
        rate, pieces, tied = replay(source, seeds)
        print(f"  {label:<36} {rate:>7.2f} pts/piece  {pieces:>6} pieces  {100 * tied:>3.0f}% tied")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PUBLISHED)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(EVAL_SEEDS))
    args = parser.parse_args()
    seeds = tuple(args.seeds)

    run_30b(args.out, seeds)
    run_tiebreak(args.out, seeds)
    run_8b(args.out, seeds)
    print(f"\nVariants written to {args.out}/ -- no model calls.")


if __name__ == "__main__":
    main()
