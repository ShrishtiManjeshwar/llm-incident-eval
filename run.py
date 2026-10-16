"""Run the agent on an incident several times and grade every brief.

    python3 run.py --incident translation_fallback_01 --runs 5
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from incident_brief.model_client import AgentError, parse_brief, write_brief
from incident_brief.check import check_brief

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description="Grade LLM-written incident briefs.")
    parser.add_argument("--incident", default="translation_fallback_01")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--pause", type=float, default=6.0, help="seconds between calls, for free-tier rate limits")
    args = parser.parse_args()

    folder = ROOT / "incidents" / args.incident
    incident_text = (folder / "logs.txt").read_text()
    key = json.loads((folder / "answer_key.json").read_text())

    results = []
    for number in range(1, args.runs + 1):
        try:
            reply = write_brief(incident_text)
        except AgentError as exc:
            print("run {}: stopped. {}".format(number, exc))
            break
        brief = parse_brief(reply["text"])
        verdict = check_brief(brief, incident_text, key)
        results.append(
            {
                "run": number,
                "model": reply["model"],
                "prompt_tokens": reply["prompt_tokens"],
                "output_tokens": reply["output_tokens"],
                "brief": brief if brief is not None else reply["text"],
                "check": verdict,
            }
        )
        status = "PASS" if verdict["passed"] else "FAIL"
        print("run {}: {}".format(number, status))
        for failure in verdict["failures"]:
            print("   - {}: {}".format(failure["rule"], failure["detail"]))
        if number < args.runs:
            time.sleep(args.pause)

    if not results:
        return 1

    passed = sum(1 for item in results if item["check"]["passed"])
    summary = {
        "incident": args.incident,
        "model": results[0]["model"],
        "runs": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "prompt_tokens": sum(item["prompt_tokens"] for item in results),
        "output_tokens": sum(item["output_tokens"] for item in results),
    }
    out_dir = ROOT / "runs"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / "{}-{}.json".format(args.incident, stamp)
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2) + "\n")

    print()
    print("{} of {} briefs passed the check.".format(passed, len(results)))
    print("saved:", out_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
