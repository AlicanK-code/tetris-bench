"""Every sweep that claims N samples must actually ask N different questions.

A sweep holds its prompt fixed on purpose, so the seed is the only thing left to
carry the variation. `ModelClient.complete` falls back to the configured seed
when none is passed, which makes omitting it silent: the sweep runs to
completion, writes N files, prints N rows, and has asked one question N times.
That happened -- `analysis/counterexample_arm.py` sampled six boards three times
each and returned byte-identical functions for two of the three on every board.

The AST test is the one that would have caught it, because the defect was a
missing keyword argument at a call site rather than bad arithmetic anywhere.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parents[1] / "analysis"

#: Sending an identical request N times is this script's entire experiment: it
#: asks whether a revision is reproducible, and a varying seed would answer a
#: different question. See its module docstring.
SWEEPS_EXEMPT_FROM_SEEDING = {"revise_reproducibility.py"}


def _load_counterexample_arm():
    """Import ``analysis/counterexample_arm.py`` by path.

    ``analysis/`` is scripts rather than an installed package, and packaging it
    only so a test can import it would let the test drive the project layout.
    """
    path = ANALYSIS / "counterexample_arm.py"
    spec = importlib.util.spec_from_file_location("tetris_counterexample_arm", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


arm = _load_counterexample_arm()


@dataclass
class StubConfig:
    seed: int | None


@dataclass
class StubClient:
    """Records the seed each call was given, and nothing else."""

    config: StubConfig
    seeds: list[int | None] = field(default_factory=list)

    def complete(self, messages: list[dict[str, str]], seed: int | None = None) -> str:
        self.seeds.append(seed)
        return "ok"


def test_consecutive_runs_of_a_sweep_get_different_seeds():
    """The defect, stated as a test: runs 10, 11 and 12 must differ."""
    client = StubClient(StubConfig(seed=1))
    for index in (10, 11, 12):
        arm.sample_once(client, "prompt", index)

    assert client.seeds == [11, 12, 13]
    assert len(set(client.seeds)) == 3


def test_a_sweep_index_offsets_the_seed_the_way_a_chain_does():
    """One derivation for both, so a sweep and a chain cannot drift apart."""
    from tetris_bench.loop import model_seed_for

    client = StubClient(StubConfig(seed=7))
    for index in range(5):
        arm.sample_once(client, "prompt", index)

    assert client.seeds == [model_seed_for(7, index) for index in range(5)]


def test_a_model_configured_without_a_seed_stays_unseeded():
    """Offsetting nothing is nothing: the provider keeps choosing."""
    client = StubClient(StubConfig(seed=None))
    arm.sample_once(client, "prompt", 3)

    assert client.seeds == [None]


def _complete_calls(tree: ast.Module) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "complete"
    ]


def test_every_analysis_sweep_passes_a_seed():
    """No analysis script may call ``complete`` without choosing a seed.

    Checked on the source rather than by running anything, because the failure
    mode is a call site that quietly falls back to the configured seed. A test
    that needed the sweep to run would need a GPU and 15 minutes per sample.
    """
    offenders: list[str] = []
    for path in sorted(ANALYSIS.glob("*.py")):
        if path.name in SWEEPS_EXEMPT_FROM_SEEDING:
            continue
        tree = ast.parse(path.read_text())
        for call in _complete_calls(tree):
            if not any(keyword.arg == "seed" for keyword in call.keywords):
                offenders.append(f"{path.name}:{call.lineno}")

    assert offenders == [], (
        "these calls fall back to the configured seed, so every sample in the "
        f"sweep sends an identical request: {offenders}. Use `sample_once`, or "
        "add the script to SWEEPS_EXEMPT_FROM_SEEDING with a reason."
    )


def test_the_exemption_list_names_scripts_that_exist():
    """A renamed script must not silently take its exemption with it."""
    for name in SWEEPS_EXEMPT_FROM_SEEDING:
        assert (ANALYSIS / name).exists(), f"{name} is exempt but does not exist"
