"""Same seed, same temperature, three times: is a sampled chain reproducible?

If yes, temperature > 0 buys diversity *across* chains without giving up
reproducibility *within* one -- chain k stays a function of (prompt, seed+k).
"""

import hashlib
import json
import urllib.request

PROMPT = "Name seven unusual fruits, one per line. No commentary."
URL = "http://localhost:11434/v1/chat/completions"


def ask(temperature: float, seed: int) -> str:
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
    return hashlib.sha256(text.encode()).hexdigest()[:12]


for temp in (1.0, 0.7):
    shas = [ask(temp, 7) for _ in range(3)]
    verdict = "reproducible" if len(set(shas)) == 1 else f"{len(set(shas))} distinct"
    print(f"temp {temp}, seed 7, three calls: {shas}  -> {verdict}")
