import json
import unittest
from pathlib import Path

from incident_brief.check import check_brief, real_line_ids

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "incidents" / "translation_fallback_01"
INCIDENT = (FOLDER / "logs.txt").read_text()
KEY = json.loads((FOLDER / "answer_key.json").read_text())

REAL_WARNING = KEY["must_cite_any"][0]
CDN_LINE = KEY["decoys"][0]["lines"][0]
TIMEOUT_LINE = KEY["decoys"][1]["lines"][0]


def good_brief(**overrides):
    brief = {
        "cause": "Release 2026.10.14.2 regenerated the locale files and keys went missing, so pages fall back to English.",
        "evidence": [REAL_WARNING],
        "next_action": "Roll back release 2026.10.14.2 and regenerate the locale files.",
        "detection": "Alert on missing-key fallback warnings per locale.",
    }
    brief.update(overrides)
    return brief


def rules(verdict):
    return {failure["rule"] for failure in verdict["failures"]}


class CheckTest(unittest.TestCase):
    def test_answer_key_points_at_real_lines(self):
        real = real_line_ids(INCIDENT)
        for line_id in KEY["must_cite_any"]:
            self.assertIn(line_id, real)
        for decoy in KEY["decoys"]:
            for line_id in decoy["lines"]:
                self.assertIn(line_id, real)

    def test_good_brief_passes(self):
        verdict = check_brief(good_brief(), INCIDENT, KEY)
        self.assertTrue(verdict["passed"], verdict)

    def test_blaming_the_cdn_change_fails(self):
        brief = good_brief(
            cause="The CDN cache TTL change is serving stale translation files.",
            evidence=[CDN_LINE],
            next_action="Revert the CDN cache TTL.",
        )
        verdict = check_brief(brief, INCIDENT, KEY)
        self.assertFalse(verdict["passed"])
        self.assertIn("wrong_cause", rules(verdict))
        self.assertIn("no_real_evidence", rules(verdict))

    def test_right_cause_without_the_version_number_passes(self):
        brief = good_brief(cause="A recent deployment rewrote the locale files and keys went missing, so pages fall back to English.")
        self.assertTrue(check_brief(brief, INCIDENT, KEY)["passed"])

    def test_blaming_slow_cdn_revalidation_fails(self):
        brief = good_brief(
            cause="A recent deployment ran, but slow origin revalidation of the locale files caused the fallback to English."
        )
        verdict = check_brief(brief, INCIDENT, KEY)
        self.assertEqual(rules(verdict), {"wrong_cause"})

    def test_a_translation_completeness_test_counts_as_detection(self):
        brief = good_brief(detection="An automated translation completeness test in CI before each release.")
        self.assertTrue(check_brief(brief, INCIDENT, KEY)["passed"])

    def test_detection_phrased_as_falling_back_counts(self):
        brief = good_brief(detection="A UI regression test that fails when a translated page falls back to English.")
        self.assertTrue(check_brief(brief, INCIDENT, KEY)["passed"])

    def test_blaming_the_timeout_fails(self):
        brief = good_brief(
            cause="The recs-service timeout is breaking the page.",
            evidence=[TIMEOUT_LINE],
        )
        verdict = check_brief(brief, INCIDENT, KEY)
        self.assertIn("wrong_cause", rules(verdict))

    def test_right_cause_with_no_real_evidence_fails(self):
        verdict = check_brief(good_brief(evidence=[CDN_LINE]), INCIDENT, KEY)
        self.assertEqual(rules(verdict), {"no_real_evidence"})

    def test_invented_line_fails(self):
        verdict = check_brief(good_brief(evidence=[REAL_WARNING, "L999"]), INCIDENT, KEY)
        self.assertIn("invented_evidence", rules(verdict))

    def test_invented_line_mentioned_in_prose_fails(self):
        verdict = check_brief(
            good_brief(cause="Release 2026.10.14.2 caused it, see L998 for the stack trace."),
            INCIDENT,
            KEY,
        )
        self.assertIn("invented_evidence", rules(verdict))

    def test_missing_detection_fails(self):
        verdict = check_brief(good_brief(detection="Add more logging."), INCIDENT, KEY)
        self.assertEqual(rules(verdict), {"no_detection"})

    def test_bad_shape_fails(self):
        self.assertEqual(rules(check_brief(None, INCIDENT, KEY)), {"format"})
        self.assertEqual(rules(check_brief({"cause": "x"}, INCIDENT, KEY)), {"format"})


if __name__ == "__main__":
    unittest.main()
