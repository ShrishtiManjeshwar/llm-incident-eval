"""Re-grade saved runs with the current check. Makes no model calls.

    python3 regrade.py runs/translation_fallback_01-<stamp>.json
"""

import json
import sys
from pathlib import Path

from incident_brief.check import check_brief

ROOT = Path(__file__).resolve().parent


def main(path):
    saved = json.loads(Path(path).read_text())
    folder = ROOT / "incidents" / saved["summary"]["incident"]
    incident_text = (folder / "logs.txt").read_text()
    key = json.loads((folder / "answer_key.json").read_text())

    for item in saved["results"]:
        item["check"] = check_brief(item["brief"], incident_text, key)

    passed = sum(1 for item in saved["results"] if item["check"]["passed"])
    saved["summary"]["passed"] = passed
    saved["summary"]["failed"] = len(saved["results"]) - passed
    Path(path).write_text(json.dumps(saved, indent=2) + "\n")
    print("{}: {} of {} pass".format(Path(path).name, passed, len(saved["results"])))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        main(arg)
