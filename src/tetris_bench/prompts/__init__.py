"""Versioned prompt templates, loaded from files rather than inlined.

Prompts are the experiment's independent variable: a change to one changes every
result after it. Keeping them in named, versioned files means a diff shows
exactly what changed and when, which inline strings scattered through agent code
would not. The version is in the filename (``strategy_v1.md``), so an old run's
prompt stays readable after a newer one exists.

Templates use ``str.format`` placeholders. They live inside the package so they
ship with it rather than depending on the repository layout at runtime.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).parent


def available() -> list[str]:
    """Every template name on disk, without extensions."""
    return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))


def load(name: str) -> str:
    """Read one template verbatim."""
    path = PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no prompt template {name!r}; available: {', '.join(available())}")
    return path.read_text(encoding="utf-8")


def render(name: str, **values: object) -> str:
    """Load a template and substitute its placeholders.

    A missing placeholder raises rather than rendering a prompt with a literal
    ``{brace}`` in it, which a model would see and be confused by.
    """
    template = load(name)
    try:
        return template.format(**values)
    except KeyError as error:
        raise KeyError(f"prompt {name!r} needs a value for {error.args[0]!r}") from None
