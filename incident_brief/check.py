"""Grade an incident brief against the answer key. Plain Python, no model.

A brief passes only if every rule holds. Each failure names the rule that
rejected it, so a miss can be explained in one sentence.
"""

import re

LINE_AT_START = re.compile(r"^(L\d{3}) ", re.MULTILINE)
LINE_ANYWHERE = re.compile(r"\bL\d{3}\b")

REQUIRED_FIELDS = {
    "cause": str,
    "evidence": list,
    "next_action": str,
    "detection": str,
}


def real_line_ids(incident_text):
    return set(LINE_AT_START.findall(incident_text))


def check_brief(brief, incident_text, key):
    failures = []

    shape = _check_shape(brief)
    if shape:
        return {"passed": False, "failures": [shape]}

    real = real_line_ids(incident_text)
    cited = [str(item).strip() for item in brief["evidence"]]
    everything = " ".join(
        [brief["cause"], brief["next_action"], brief["detection"]] + cited
    )

    invented = sorted({lid for lid in LINE_ANYWHERE.findall(everything) if lid not in real})
    if invented:
        failures.append(
            {
                "rule": "invented_evidence",
                "detail": "cites lines that are not in the incident: {}".format(", ".join(invented)),
            }
        )

    if not set(cited) & set(key["must_cite_any"]):
        failures.append(
            {
                "rule": "no_real_evidence",
                "detail": "cites none of the lines that prove the cause ({})".format(
                    ", ".join(key["must_cite_any"])
                ),
            }
        )

    cause = brief["cause"].lower()
    release_words = [word.lower() for word in key["must_name_as_cause"] + key["release_words"]]
    names_release = any(word in cause for word in release_words)
    blamed = [
        decoy["id"]
        for decoy in key["decoys"]
        if any(word in cause for word in decoy["keywords"])
    ]
    if not names_release or blamed:
        parts = []
        if not names_release:
            parts.append("cause does not point at the release")
        if blamed:
            parts.append("it blames a decoy ({})".format(", ".join(blamed)))
        failures.append({"rule": "wrong_cause", "detail": "; ".join(parts)})

    detection = brief["detection"].lower()
    about_translations = any(word in detection for word in key["detection_topics"])
    proposes_a_check = any(word in detection for word in key["detection_actions"])
    if not (about_translations and proposes_a_check):
        failures.append(
            {
                "rule": "no_detection",
                "detail": "does not propose a test, alert or check about translations, locales or fallbacks",
            }
        )

    return {"passed": not failures, "failures": failures}


def _check_shape(brief):
    if not isinstance(brief, dict):
        return {"rule": "format", "detail": "brief is not a JSON object"}
    for field, kind in REQUIRED_FIELDS.items():
        if not isinstance(brief.get(field), kind):
            return {"rule": "format", "detail": "field '{}' is missing or the wrong type".format(field)}
    return None
