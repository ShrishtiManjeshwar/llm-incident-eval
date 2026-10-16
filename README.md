# LLM incident eval

A small evaluation for LLM output that has no single correct string. The idea: grade a model's answer against a ground-truth answer key, and plant decoys so that a wrong answer can look right.

The worked example is incident diagnosis. A model reads a noisy production log and writes a short brief: the likely cause, the log lines that support it, one next action, and one check that would have caught the problem earlier. A plain-Python check then grades the brief. The check calls no model.

The incident is invented. It is modeled on a real failure shape: a release silently breaks translations, nothing errors, and a customer notices hours later.

## What each file is for

| Path | Role |
| --- | --- |
| `incidents/translation_fallback_01/logs.txt` | **Fed to the model.** The only thing it sees. |
| `incidents/translation_fallback_01/answer_key.json` | **Used only for grading.** The model never sees it. |
| `incident_brief/check.py` | The rules that grade a brief. |
| `incident_brief/model_client.py` | Sends the log to Gemini and returns the reply. |
| `run.py` | Runs the model N times and grades each brief. |
| `regrade.py` | Re-grades saved runs with the current check, with no model calls. |
| `generate_incident.py` | Writes `logs.txt` and `answer_key.json` from a fixed seed. |
| `tests/test_check.py` | Tests for the check, using hand-written briefs. |
| `runs/` | Saved model outputs and their grades. |

## The incident

`logs.txt` is about 390 numbered lines: page requests, health checks, metrics, unrelated warnings, and one release.

- A release rewrites the static locale files. German, French and Japanese lose some keys, and the app silently falls back to English.
- 5xx rate and latency stay flat the whole time. The only runtime evidence is six sampled `missing key ... fallback=en-US` warnings, buried among harmless missing-key warnings for an unrelated English string.
- Two decoys. A CDN cache TTL change shortly before the release, followed by CDN log lines about slow origin revalidation: it looks like a cache problem. And a single timeout from an unrelated recommendations service, the only line that says "timeout".

## The check

`incident_brief/check.py` rejects a brief when any rule fails:

| Rule | Rejects a brief that... |
| --- | --- |
| `invented_evidence` | cites a log line that is not in the incident |
| `no_real_evidence` | cites none of the six lines that prove the cause |
| `wrong_cause` | does not point at the release, or names a decoy as a cause (CDN, slow revalidation, the timeout) |
| `no_detection` | proposes no test, alert or check about translations, locales or fallbacks |

`wrong_cause` is strict on purpose: a brief that lists the right cause next to a wrong one fails.

The rules are keyword-based. While building it I found several cases where the check wrongly rejected a correct brief (it wanted the exact version string, and exact wording like "fallback" when the brief said "falling back"). I fixed the rules and added a test for each. `regrade.py` re-grades saved briefs with the current check, so fixing the check does not need new model calls.

## Results

Same log, same prompt, temperature 0.7. Raw outputs are in `runs/`.

| Model | Briefs passing the check |
| --- | --- |
| `gemini-3.5-flash-lite` | 0 of 10 |
| `gemini-3.5-flash` | 5 of 5 |

The smaller model got it wrong in two ways:

- 6 of 10 never pointed at the release. Most grabbed the one timeout warning and called it the cause. Run 1 cites only that line: *"An upstream timeout from the recommendations service occurred during request handling."*
- 4 of 10 named the release and the missing keys, then also blamed the timeout or the CDN.

Seven of the ten cited none of the lines that actually prove the cause.

The timeout is a decoy: one call, to a recommendations service, with nothing to do with page text. The tickets say the German and French pages are in English, and the missing-key warnings begin right after the release and not before.

## What I got wrong first

- The first version of the log began with a line naming the incident, which hinted at the answer. I removed it and reran. On the old log the smaller model blamed the CDN; on the clean one it blamed the timeout. A small change to the input moved what it blamed, which is a reason not to read much into one incident.
- The first rules rejected correct briefs, as described above.

## Limits

- One incident. Two decoys show the check is not trivial. They are not enough to say how good a model is at diagnosis.
- Small samples: 10 runs and 5 runs.
- The check is keyword-based. Near-correct briefs can be wrongly rejected, and the strict `wrong_cause` rule is a design choice, not the only reasonable one.
- Free-tier terms: prompts may be used by Google to improve its products. Nothing here is real or confidential.

## Run it

```bash
cp .env.example .env        # then paste your Gemini API key after GEMINI_API_KEY=
python3 -m unittest tests.test_check
python3 run.py --runs 5     # or: GEMINI_MODEL=gemini-3.5-flash-lite python3 run.py --runs 10
python3 regrade.py runs/<file>.json
```

Python 3.9+ and the standard library only.

## Next

- A second incident where the true cause is the decoy, to test that the check does not just reward blaming the release.
- Replace the keyword rules with a rubric, and measure how often it agrees with a human reading.
- Record token cost per brief and compare models on cost against pass rate.
