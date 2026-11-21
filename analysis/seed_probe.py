"""Does the seed change the output at temperature 0?

Greedy decoding takes the argmax at every step and never draws from the RNG, so
the seed should be inert at temperature 0 and live above it. This is a thinking
model, so the reasoning trace is where a short generation's tokens actually go --
hash the whole message, not just `content`.
"""

import hashlib
import json
import urllib.request

PROMPT = "Name seven unusual fruits, one per line. No commentary."
URL = "http://localhost:11434/v1/chat/completions"


def ask(temperature: float, seed: int) -> tuple[str, str]:
    body = json.dumps(
        {
            "model": "qwen3:14b",
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": temperature,
            "seed": seed,
            "max_tokens": 120,
        }
    ).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        msg = json.load(r)["choices"][0]["message"]
    text = (msg.get("reasoning") or "") + "\x00" + (msg.get("content") or "")
    return hashlib.sha256(text.encode()).hexdigest()[:12], text.strip()[:56].replace("\n", " ")


for temp in (0.0, 1.0):
    print(f"--- temperature {temp} ---")
    for seed in (1, 2, 3):
        sha, head = ask(temp, seed)
        print(f"  seed {seed}: {sha}  {head!r}")
