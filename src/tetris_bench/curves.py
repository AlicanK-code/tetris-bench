"""Turning a loop log into an improvement curve.

This is the measurement half of the benchmark. The loop produces rows; this
decides what those rows mean. Four choices are made here explicitly rather than
left to a dataframe one-liner, because each of them can manufacture a result.

**The curve is read from evaluation rows.** A function revised against a
training sequence has been selected against it, and the project has already
recorded a training-seed score of 400 that was a function's luckiest case out of
twenty-one rather than its typical one (held-out mean 110). Reading the curve
from training rows would report that 400.

**Deltas are paired within a chain.** Chains never see each other's functions, so
chain 2's iteration 3 is not a revision of chain 1's iteration 2. Subtracting
cross-chain means at consecutive iterations would mix independent lineages and
attribute the difference between two chains to an act of revision. Every delta
here is ``score[i] - score[i-1]`` inside one chain.

**Chains are combined by median, never by best-of.** Best-so-far rises about 97%
under pure noise, because taking a maximum over an increasing number of samples
increases regardless of whether anything improved. :meth:`Curve.best_so_far`
exists because the spec asks for it, but it is a selection statistic and not
evidence of learning.

**Generation cost lives on training rows only.** ``loop._log_multi`` attributes a
position's usage to its first row and zeroes the rest, and evaluation games are
logged with no usage at all because the model was never called for them. So a
position's cost must be summed across its *training* rows while its score is read
from its *evaluation* rows. Filtering to ``split == "eval"`` and summing tokens
yields zero, which reads as a free run rather than as a bug.

The module is pure and stdlib-only: it takes dicts and returns dataclasses, so it
is unit-testable without pandas, a real log, or a model. ``analysis/curves.py``
is the command-line front end.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

#: A position whose function never ran contributes a real zero, not a gap. A
#: model that emitted unusable code at iteration 3 did not score nothing by bad
#: luck, and dropping the row would quietly reward it by shortening its curve.
#: The count is kept separately so a zero from a rejection stays distinguishable
#: from a zero from a terrible strategy.
REJECTED_SCORE = 0.0


@dataclass(frozen=True)
class PositionSummary:
    """One (model, chain, iteration) position, aggregated over its games.

    Scores are means over the evaluation seeds; cost is summed over the training
    rows, which is where the loop records it. ``train_score`` is carried for
    comparison only -- the gap between it and ``eval_score`` is how far a
    revision was tuned to the sequences it saw.
    """

    model: str
    chain: int
    iteration: int
    eval_games: int
    eval_score: float
    #: Median held-out score, reported beside the mean because Tetris scores are
    #: heavy-tailed: surviving longer clears more lines, so score grows
    #: superlinearly with competence. The first real loop position measured a
    #: mean of 1,580 against a median of 400 — one sequence scored 11,000 and
    #: every other was under 2,300. The mean is not wrong (that upside is real
    #: competence, and ten seeds exist to average over it) but a mean and a
    #: median this far apart is the signal that one sequence is carrying the
    #: number, and a reader has to be able to see it.
    eval_median: float
    #: Spread of this position's score across the held-out seeds. A fixed,
    #: deterministic function varies 85-348% across seeds it has not seen, so an
    #: iteration-to-iteration difference smaller than this is not a difference.
    #: It is also the only non-arbitrary source for a plateau threshold.
    eval_sd: float
    #: ``None``, not ``0.0``, when no held-out game was logged. A zero hole
    #: count reads as a *flawless* board, so a position that never played would
    #: otherwise enter any average as the best result in the run. The score
    #: keeps its zero -- scoring nothing is a real outcome -- but a board that
    #: does not exist has no features.
    eval_pieces: float | None
    eval_holes: float | None
    train_games: int
    train_score: float
    played: bool
    rejected: bool
    function_sha: str
    tokens_in: int
    tokens_out: int
    seconds: float
    model_calls: int

    @property
    def tokens(self) -> int:
        """Prompt plus completion. The benchmark's cost unit, since every run is local."""
        return self.tokens_in + self.tokens_out

    @property
    def score(self) -> float:
        """The number the curve is read from."""
        return self.eval_score


def _mean(values: Sequence[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _sd(values: Sequence[float]) -> float:
    """Sample standard deviation, zero for fewer than two values.

    Zero rather than an error: one held-out game has no measurable spread, which
    is a fact about the sample size and not a failure to compute.
    """
    return statistics.stdev(values) if len(values) > 1 else 0.0


def summarise(rows: Iterable[dict]) -> list[PositionSummary]:
    """Collapse log rows into one summary per position, in chain-major order.

    Rows for other modes are ignored rather than rejected, so a log that also
    holds baseline games stays readable.
    """
    grouped: dict[tuple[str, int, int], list[dict]] = {}
    # One row per game, keyed by everything that identifies a game. Cost is
    # summed over a position's rows, so a duplicated row silently doubles that
    # position's tokens while leaving every score untouched -- the kind of error
    # nothing in a table looks wrong about. `completed_positions` prevents it
    # within one run; concatenating two logs does not.
    seen: set[tuple[str, int, int, int, str]] = set()
    for row in rows:
        if row.get("mode") != "strategy":
            continue
        model = str(row.get("model", ""))
        chain = int(row.get("chain", 0))
        iteration = int(row.get("iteration", 0))
        identity = (model, chain, iteration, int(row.get("seed", -1)), str(row.get("split", "")))
        if identity in seen:
            continue
        seen.add(identity)
        grouped.setdefault((model, chain, iteration), []).append(row)

    summaries: list[PositionSummary] = []
    for (model, chain, iteration), group in sorted(grouped.items()):
        train = [r for r in group if r.get("split") == "train"]
        held_out = [r for r in group if r.get("split") == "eval"]

        # A position with no evaluation rows never got that far: the function was
        # rejected or crashed, so the loop logged training rows and moved on.
        # Its contribution to the curve is a zero, which is what happened.
        # "Nothing in this position ever played", which is the same definition
        # `loop.unplayed_positions` uses -- deliberately, so the two modules
        # cannot disagree about what a failed position is. It must not be "any
        # row says unplayed": a crash part-way through the training sequences
        # now logs the games that finished alongside zeroed rows for the ones
        # that never ran, and that position would otherwise be labelled rejected
        # despite having a full set of good held-out games.
        rejected = not any(r.get("played", True) for r in group)
        eval_scores = [float(r["score"]) for r in held_out]
        eval_score = _mean(eval_scores) if held_out else REJECTED_SCORE

        summaries.append(
            PositionSummary(
                model=model,
                chain=chain,
                iteration=iteration,
                eval_games=len(held_out),
                eval_score=eval_score,
                eval_median=statistics.median(eval_scores) if eval_scores else REJECTED_SCORE,
                eval_sd=_sd(eval_scores),
                eval_pieces=(
                    _mean([float(r["pieces_placed"]) for r in held_out]) if held_out else None
                ),
                eval_holes=(
                    _mean([float(r["final_holes"]) for r in held_out]) if held_out else None
                ),
                train_games=len(train),
                train_score=_mean([float(r["score"]) for r in train]),
                played=not rejected,
                rejected=rejected,
                function_sha=str(group[0].get("function_sha", "")),
                # Summed over the whole group, not over `held_out`: the loop puts
                # usage on the first training row and zeroes the others, so this
                # is the position's single generation counted once.
                tokens_in=sum(int(r.get("tokens_in", 0)) for r in group),
                tokens_out=sum(int(r.get("tokens_out", 0)) for r in group),
                seconds=sum(float(r.get("latency_seconds", 0.0)) for r in group),
                model_calls=sum(int(r.get("model_calls", 0)) for r in group),
            )
        )
    return summaries


@dataclass(frozen=True)
class Curve:
    """One model's improvement curve, with the derived series the spec asks for."""

    model: str
    positions: list[PositionSummary]

    @property
    def chains(self) -> list[int]:
        return sorted({p.chain for p in self.positions})

    @property
    def iterations(self) -> list[int]:
        return sorted({p.iteration for p in self.positions})

    def seed_noise(self) -> float:
        """Spread of a *single* held-out game within a position.

        The median of the per-position standard deviations: the variation of one
        fixed function across sequences it never saw, with the model held
        constant. Useful for describing how noisy one game is, and **wrong as a
        bar for a change between iterations** -- see :meth:`delta_noise`.
        """
        spreads = [p.eval_sd for p in self.positions if p.eval_games > 1]
        return statistics.median(spreads) if spreads else 0.0

    def noise_of_mean(self) -> float:
        """Spread of the plotted point, which is a mean of ``n`` held-out games.

        Smaller than :meth:`seed_noise` by √n. Comparing a mean of ten games
        against a one-game spread sets the bar about three times too high, which
        reports a real gain as noise.
        """
        counts = [p.eval_games for p in self.positions if p.eval_games > 1]
        if not counts:
            return 0.0
        return self.seed_noise() / math.sqrt(statistics.median(counts))

    def chain_spread(self) -> float:
        """Disagreement between independent chains at the same iteration.

        This is **generation** noise: chains run the same prompt sequence and
        differ only in what the model happened to produce. The project has
        measured it to be large — three near-identical prompts on this rung gave
        held-out 2,540, 120 and 5 — so it dominates seed noise rather than
        adding to it.

        ``0.0`` when there is only one chain, which is not a claim that
        generation noise is absent, only that this log cannot see it.
        """
        spreads = [
            _sd([p.score for p in self.positions if p.iteration == iteration])
            for iteration in self.iterations
        ]
        usable = [s for s in spreads if s > 0.0]
        return statistics.median(usable) if usable else 0.0

    def delta_noise(self) -> float:
        """The bar a change between iterations has to clear.

        Two independent noise sources, and the larger one governs:

        - **generation noise** (:meth:`chain_spread`) -- two chains given the
          same prompt produce different functions. Measured to be the bigger
          term by far, so when the log has several chains this is the bar.
        - **seed noise on the plotted mean** (:meth:`noise_of_mean`) -- the only
          term a single-chain log can estimate, and an underestimate of the
          truth, because it holds the function fixed and so cannot see
          generation noise at all.

        A single-chain curve therefore gets a bar that is known to be too
        lenient. That is an argument for running several chains, not for
        inventing a correction here.
        """
        return max(self.chain_spread(), self.noise_of_mean())

    def chain_series(self, chain: int) -> list[PositionSummary]:
        """One chain's positions in iteration order: a single lineage."""
        return sorted((p for p in self.positions if p.chain == chain), key=lambda p: p.iteration)

    def median_score(self) -> list[float]:
        """Median evaluation score across chains, one value per iteration.

        Median rather than mean because a single chain that produces an
        unplayable function contributes a zero, and a mean of three chains would
        let that one zero dominate a result the other two agree on.
        """
        series: list[float] = []
        for iteration in self.iterations:
            scores = [p.score for p in self.positions if p.iteration == iteration]
            series.append(statistics.median(scores) if scores else 0.0)
        return series

    def best_so_far(self) -> list[float]:
        """Running maximum of :meth:`median_score`.

        **Read this with suspicion.** A running maximum over a growing sample
        rises even when nothing improves -- about 97% under this project's own
        noise floor. It is reported because the spec lists it, and because a
        best-so-far curve that rises no faster than the noise floor is itself the
        finding.
        """
        best: list[float] = []
        running = float("-inf")
        for value in self.median_score():
            running = max(running, value)
            best.append(running)
        return best

    def paired_deltas(self) -> list[tuple[int, int, float]]:
        """Every within-chain step as ``(chain, iteration, delta)``.

        ``iteration`` is the later of the pair, so a delta at iteration 1 is the
        effect of the first revision.
        """
        deltas: list[tuple[int, int, float]] = []
        for chain in self.chains:
            series = self.chain_series(chain)
            for earlier, later in zip(series, series[1:], strict=False):
                deltas.append((chain, later.iteration, later.score - earlier.score))
        return deltas

    def mean_delta(self) -> float:
        """Mean within-chain improvement per revision.

        **This is a telescoping sum.** The mean of a chain's deltas is exactly
        its first-to-last difference divided by the number of steps, because
        every intermediate value cancels, so this row carries no information
        that :meth:`score_gained` does not — while reading as a statement about
        typical revisions. A curve can report +183 "per revision" with a worst
        step of −936 and a best of +1,203. Always report
        :meth:`median_abs_delta` beside it.
        """
        return _mean([delta for _, _, delta in self.paired_deltas()])

    def median_abs_delta(self) -> float:
        """Typical size of a within-chain step, regardless of direction.

        The number :meth:`mean_delta` cannot give: how far a revision actually
        moves things. A model whose net is +3 while its typical step is 15 is
        not inching forward, it is being thrown about.
        """
        sizes = [abs(delta) for _, _, delta in self.paired_deltas()]
        return statistics.median(sizes) if sizes else 0.0

    def fall_from_peak(self) -> float:
        """How far the median ended below its best. Zero if it ended at its peak.

        A drawdown larger than :meth:`delta_noise` means the model got worse
        after its best iteration, which is a finding in its own right and is
        otherwise only visible by eyeballing the rows.
        """
        medians = self.median_score()
        return max(medians) - medians[-1] if medians else 0.0

    def regressions(self) -> int:
        """Within-chain steps where the held-out score fell.

        A revision that makes things worse is a real result, and a curve that
        rises on average while regressing half the time is a different claim from
        one that rises monotonically.
        """
        return sum(1 for _, _, delta in self.paired_deltas() if delta < 0)

    def regressions_beyond(self, bar: float) -> int:
        """Within-chain steps that fell by more than ``bar``.

        :meth:`regressions` uses a zero threshold, which contradicts the rest of
        the report: a fall of 0.9 points counts while a rise of 11 is dismissed
        as noise on the same page. Both numbers belong in the output.
        """
        return sum(1 for _, _, delta in self.paired_deltas() if delta < -bar)

    def chain_spread_range(self) -> tuple[float, float]:
        """Smallest and largest between-chain spread across the iterations.

        :meth:`chain_spread` is a median over iterations, and the quantity can
        vary tenfold: a measured sequence was 103, 134, 533, 138, 737, 76 against
        a median of 136, so a per-step judgement at the fifth iteration used a
        bar five times too small. The summary quotes one number; this says how
        much that single number is hiding.
        """
        spreads = [
            _sd([p.score for p in self.positions if p.iteration == iteration])
            for iteration in self.iterations
        ]
        usable = [s for s in spreads if s > 0.0]
        return (min(usable), max(usable)) if usable else (0.0, 0.0)

    def qualifying_chains(self) -> list[int]:
        """Chains whose first-to-last gain clears :meth:`delta_noise`.

        These are the only chains :meth:`tokens_per_point` divides by, so the
        tokens the others spent do not appear in that figure. The gate is right
        — dividing by a gain inside the noise yields absurdities like 312,000
        tokens per point — but a cost figure resting on two thirds of the spend
        has to say so.
        """
        bar = self.delta_noise()
        qualifying: list[int] = []
        for chain in self.chains:
            series = self.chain_series(chain)
            if len(series) < 2:
                continue
            gained = series[-1].score - series[0].score
            if gained > 0 and gained > bar:
                qualifying.append(chain)
        return qualifying

    def plateau_iteration(self, tolerance: float) -> int | None:
        """First iteration that comes within ``tolerance`` of the curve's **peak**.

        The peak, not the last value: a curve that reaches 2,000 at iteration 1
        and collapses to 100 by iteration 5 has its best at 1. This answers "when
        did it stop getting better", which is not the same question as "where did
        it end up" -- read it beside :meth:`score_gained`, which is signed, or a
        peak-then-collapse reads as "settled early".

        ``tolerance`` has to be supplied; :meth:`delta_noise` is the defensible
        choice. There is no default: with ``0.0`` any wobble counts as continued
        improvement, and any other constant is just a restatement of itself.
        """
        medians = self.median_score()
        if not medians:
            return None
        target = max(medians)
        for index, value in enumerate(medians):
            if value >= target - tolerance:
                return self.iterations[index]
        return None

    def incomplete_positions(self) -> list[PositionSummary]:
        """Positions whose held-out set is short, so their mean is under-sampled.

        A mean over three games pooled into the same median as means over ten is
        not wrong so much as unmarked, and the loop's resume path cannot notice:
        ``completed_positions`` counts training rows only. These have to be
        reported rather than averaged quietly.
        """
        expected = max((p.eval_games for p in self.positions), default=0)
        return [p for p in self.positions if 0 < p.eval_games < expected]

    def unlogged_positions(self) -> list[PositionSummary]:
        """Positions with no held-out game at all, which score zero in the curve.

        Two different causes, and the distinction matters: the function was
        rejected or crashed (``rejected``), or the evaluation games were never
        written — a crash on the first held-out sequence, or a run killed between
        the training and evaluation writes. The second is a gap in the log, not a
        result, and a reader must not see it as an ordinary zero.
        """
        return [p for p in self.positions if p.eval_games == 0]

    def total_tokens(self) -> int:
        return sum(p.tokens for p in self.positions)

    def total_seconds(self) -> float:
        return sum(p.seconds for p in self.positions)

    def score_gained(self) -> float:
        """Final median minus iteration-0 median."""
        medians = self.median_score()
        if len(medians) < 2:
            return 0.0
        return medians[-1] - medians[0]

    def _per_chain_cost(self, attribute: str) -> float | None:
        """Median over chains of one chain's cost per point of its own gain.

        Per chain, not per curve. Dividing *total* cost by the gain in the
        *median* charges every lineage's tokens against one lineage's
        improvement, so the figure scales with the number of chains: the same
        model at 5 chains looks five times more expensive per point than at 1.
        The ladder table compares models side by side and the project runs
        different rungs at different chain counts, so that would have been a
        straight artefact of the sampling budget.

        Only chains whose gain clears :meth:`delta_noise` count. A chain that
        ended 0.1 points up has not improved, and dividing by 0.1 produced
        figures like 312,000 tokens per point — arithmetically correct, and in a
        results table indistinguishable from a measurement. ``None`` when no
        chain gained more than the noise, which is the honest answer for a flat
        model rather than a very large number.
        """
        bar = self.delta_noise()
        ratios: list[float] = []
        for chain in self.chains:
            series = self.chain_series(chain)
            if len(series) < 2:
                continue
            gained = series[-1].score - series[0].score
            if gained <= 0 or gained <= bar:
                continue
            spent = sum(getattr(p, attribute) for p in series)
            ratios.append(spent / gained)
        return statistics.median(ratios) if ratios else None

    def tokens_per_point(self) -> float | None:
        """Tokens spent per point of held-out score gained, per chain."""
        return self._per_chain_cost("tokens")

    def seconds_per_point(self) -> float | None:
        """Wall-clock seconds per point of held-out score gained, per chain."""
        return self._per_chain_cost("seconds")


def build_curves(rows: Iterable[dict]) -> list[Curve]:
    """One curve per model in the log, ordered by model name."""
    summaries = summarise(rows)
    by_model: dict[str, list[PositionSummary]] = {}
    for summary in summaries:
        by_model.setdefault(summary.model, []).append(summary)
    return [Curve(model=model, positions=by_model[model]) for model in sorted(by_model)]
