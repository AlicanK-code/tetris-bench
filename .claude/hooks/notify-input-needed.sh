#!/bin/sh
# Push an ntfy notification when Claude Code is waiting on the user.
#
# Wired to the Notification hook in .claude/settings.local.json. Reads the hook
# payload as JSON on stdin; the topic comes from NTFY_TOPIC in the project's
# gitignored .env, because the hook does not inherit that shell environment.
#
# Deliberately quiet about *what* Claude is doing. On the public ntfy.sh the
# topic name is the only access control, so this sends the event type and the
# project directory and not the notification text, which can name files or
# quote work in progress. To include it, swap the BODY line for the commented
# one below -- knowing it leaves the machine.
set -u

ENV_FILE="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)/.env"
[ -r "$ENV_FILE" ] || exit 0

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a
[ -n "${NTFY_TOPIC:-}" ] || exit 0

PAYLOAD="$(cat)"
# stderr discarded and the result defaulted: a hook that printed a jq parse
# error on an unexpected payload would show up as hook noise on every
# notification, which is worse than a slightly vaguer message.
PROJECT="$(printf '%s' "$PAYLOAD" | jq -r '.cwd // "" | split("/") | last' 2>/dev/null)"
[ -n "$PROJECT" ] || PROJECT="claude-code"

BODY="Waiting for you in ${PROJECT}."
# BODY="$(printf '%s' "$PAYLOAD" | jq -r '.message // "Waiting for you."')"   # leaks detail

printf '%s' "$BODY" | curl -sS --max-time 10 \
  -H "Title: Claude Code" \
  -H "Priority: 4" \
  -H "Tags: bell" \
  --data-binary @- \
  "https://ntfy.sh/${NTFY_TOPIC}" >/dev/null
