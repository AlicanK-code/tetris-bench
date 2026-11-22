"""Push a short message to a phone or desktop via ntfy.

A sweep runs for hours, so the useful thing is to be told when it finishes
rather than to sit watching a log. ntfy is a publish/subscribe service: this
module POSTs to ``https://ntfy.sh/<topic>`` and anything subscribed to that
topic gets a notification.

**The topic name is the only access control.** On the public ntfy.sh server
there is no account and no key -- whoever knows the topic can both read and
publish. So the topic is treated as a secret (read from the environment, like
the model API keys) and it must be unguessable. The corollary matters more:
anything sent here is readable by anyone who learns or guesses the name, so
messages carry run statistics and nothing else.

Stdlib only, deliberately: this is a nicety bolted onto a benchmark, and it is
not worth a dependency.

    export NTFY_TOPIC=...            # or: set -a; source .env; set +a
    uv run python -m tetris_bench.notify "sweep finished"
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Sequence

#: Environment variable holding the topic. Named rather than hardcoded for the
#: same reason the model keys are: the value is a secret and must not be in git.
TOPIC_ENV = "NTFY_TOPIC"

DEFAULT_SERVER = "https://ntfy.sh"

#: ntfy's own scale: 1 is min, 3 is default, 5 bypasses do-not-disturb.
PRIORITY_DEFAULT = 3
PRIORITY_HIGH = 4


class NotifyError(Exception):
    """A notification could not be sent."""


def resolve_topic(topic: str | None = None, environ: dict[str, str] | None = None) -> str:
    """Find the topic to publish to, preferring an explicit argument.

    Raises rather than guessing, because silently publishing to a default topic
    name would be publishing to a topic a stranger may already be subscribed to.
    """
    if topic:
        return topic
    env = os.environ if environ is None else environ
    found = env.get(TOPIC_ENV, "").strip()
    if not found:
        raise NotifyError(
            f"no topic: set {TOPIC_ENV} in the environment, or pass topic= explicitly"
        )
    return found


def send(
    message: str,
    *,
    title: str | None = None,
    priority: int = PRIORITY_DEFAULT,
    tags: Sequence[str] = (),
    topic: str | None = None,
    server: str = DEFAULT_SERVER,
    timeout: float = 10.0,
) -> bool:
    """Publish one notification. Returns whether it was delivered.

    This never raises on a network or server failure, and that is the whole
    point of the return value. A notification is peripheral to the run it
    reports on, so a dropped connection must not take down a five-hour sweep --
    the same reasoning as treating a failed model call as a logged failure
    rather than the end of the run. A *configuration* mistake does raise, since
    an unset topic is a bug to fix rather than weather to ride out.
    """
    resolved = resolve_topic(topic)
    headers = {"Priority": str(priority)}
    if title:
        headers["Title"] = title
    if tags:
        headers["Tags"] = ",".join(tags)

    request = urllib.request.Request(
        f"{server.rstrip('/')}/{resolved}",
        data=message.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as error:
        # Printed, not raised: the caller is usually a finished run whose real
        # result is already safely on disk.
        print(f"notification failed: {error}", file=sys.stderr)
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    """Send the command-line arguments as one message."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        delivered = send(" ".join(args), title="tetris-bench")
    except NotifyError as error:
        print(error, file=sys.stderr)
        return 2
    return 0 if delivered else 1


if __name__ == "__main__":
    raise SystemExit(main())
