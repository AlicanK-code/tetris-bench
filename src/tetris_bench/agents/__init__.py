"""Agents: the things that choose placements.

:class:`Agent` is the interface, :data:`ScoringFunction` is the primitive that
``strategy`` mode is built on, and :class:`ScoringAgent` bridges the two.
"""

from tetris_bench.agents.base import Agent, ScoringAgent, ScoringFunction
from tetris_bench.agents.heuristic import (
    DEFAULT_WEIGHTS,
    HeuristicWeights,
    heuristic_agent,
    heuristic_scorer,
)
from tetris_bench.agents.random_agent import RandomAgent

__all__ = [
    "DEFAULT_WEIGHTS",
    "Agent",
    "HeuristicWeights",
    "RandomAgent",
    "ScoringAgent",
    "ScoringFunction",
    "heuristic_agent",
    "heuristic_scorer",
]
