"""Computes the 'before' numbers from the saved stage-1 run logs.
Usage: python scripts/stage1_stats.py assets/stage1_v0
Writes STATS.md next to the logs."""
import re
import sys
from collections import Counter
from pathlib import Path

LOGS = ["noLocalJustAPI.txt", "LocalAndAPI.txt", "LocalNoAPI.txt",
        "out_first100query.txt", "out_212queryL_A.txt"]


def read(path):
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-8"):
        try:
            text = raw.decode(enc)
            if "QUERY" in text:
                return text
        except UnicodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def stats(text):
    blocks = [b for b in text.split("=" * 70) if "QUERY:" in b]
    zero_active = sum(1 for b in blocks if "[LOCAL]" not in b and "[API]" not in b)
    errors = Counter()
    for line in text.splitlines():
        if "Eroare" in line:
            m = re.search(r"\b(\d{3}) [A-Z_]+", line)  # first code only, once per error line
            errors[m.group(1) if m else "other"] += 1
    return {
        "queries": len(blocks),
        "api_requests": text.count("Trimit request"),
        "api_ok": text.count("Raspuns primit"),
        "api_errors": sum(errors.values()),
        "error_codes": dict(errors),
        "fallbacks": text.count("Brute-Mode Fallback"),
        "zero_active": zero_active,
    }


def main(folder):
    folder = Path(folder)
    lines = ["# Stage 1 baseline (before any fix)\n",
             "| log | queries | API calls | API ok | API errors | fallbacks | queries with 0 active conditions |",
             "|---|---|---|---|---|---|---|"]
    for name in LOGS:
        path = folder / name
        if not path.exists():
            print("missing:", path)
            continue
        s = stats(read(path))
        calls = f"{s['api_requests']} ({s['api_requests'] / max(s['queries'], 1):.0%})"
        lines.append(f"| {name} | {s['queries']} | {calls} | {s['api_ok']} | "
                     f"{s['api_errors']} {s['error_codes']} | {s['fallbacks']} | {s['zero_active']} |")
    out = folder / "STATS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "assets/stage1_v0")
