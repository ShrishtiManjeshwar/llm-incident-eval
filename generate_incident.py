"""Build logs.txt and answer_key.json for translation_fallback_01.

The incident is invented. Ordinary traffic is generated with a fixed seed so the
file is reproducible. The handful of lines that matter are tagged, and the
answer key is written from their final line numbers.
"""

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "incidents" / "translation_fallback_01"
DAY = datetime(2026, 10, 14, tzinfo=timezone.utc)


def at(hms):
    h, m, s = (int(part) for part in hms.split(":"))
    return DAY + timedelta(hours=h, minutes=m, seconds=s)


def stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def key_events():
    """Lines that carry the story. Each is (time, source, message, tag)."""
    return [
        (at("13:57:40"), "change-log", "CHG-4821 cdn-edge: cache TTL for /static/* changed from 3600s to 86400s (owner=platform)", "cdn_change"),
        (at("14:01:55"), "deploy-bot", "INFO release=2026.10.14.2 service=web-frontend started steps=build,sync-static,invalidate-cache", "release_start"),
        (at("14:02:31"), "deploy-bot", "INFO sync-static completed files=4", None),
        (at("14:02:44"), "deploy-bot", "INFO invalidate-cache completed paths=/static/locales/*", "invalidated"),
        (at("14:02:45"), "deploy-bot", "INFO release=2026.10.14.2 status=succeeded", None),
        (at("14:02:46"), "cdn-edge", "INFO purge propagated paths=/static/locales/* pops=12", None),
        (at("14:04:12"), "cdn-edge", "WARN origin revalidation slow path=/static/locales/de-DE.json ms=410", None),
        (at("14:06:40"), "cdn-edge", "WARN origin revalidation slow path=/static/locales/fr-FR.json ms=388", None),
        (at("14:03:20"), "web", "WARN i18n missing key=header.title locale=de-DE fallback=en-US sampled=1/60s", "warn_1"),
        (at("14:04:20"), "web", "WARN i18n missing key=header.title locale=ja-JP fallback=en-US sampled=1/60s", "warn_2"),
        (at("14:05:20"), "web", "WARN i18n missing key=nav.tooltip.cart locale=fr-FR fallback=en-US sampled=1/60s", "warn_3"),
        (at("15:12:40"), "web", "WARN upstream timeout service=recs-service path=/api/recs count=1", "recs_timeout"),
        (at("15:41:10"), "web", "WARN i18n missing key=nav.tooltip.cart locale=de-DE fallback=en-US sampled=1/60s", "warn_4"),
        (at("16:20:35"), "web", "WARN i18n missing key=header.title locale=fr-FR fallback=en-US sampled=1/60s", "warn_5"),
        (at("16:33:50"), "web", "WARN i18n missing key=nav.tooltip.cart locale=ja-JP fallback=en-US sampled=1/60s", "warn_6"),
        (at("16:47:30"), "support-ticket", "TKT-9132 \"German storefront shows the page title and tooltips in English\"", None),
        (at("16:49:05"), "support-ticket", "TKT-9135 \"French cart page tooltip is in English\"", None),
    ]


def noise_events(rng):
    events = []
    start, end = at("13:30:00"), at("16:50:00")
    deploy_done = at("14:02:45")

    moment = start
    while moment < end:
        moment += timedelta(seconds=rng.randint(20, 70))
        locale = rng.choices(["en", "de", "fr", "ja"], weights=[5, 2, 2, 1])[0]
        page = rng.choice(["home", "cart", "product/123", "product/884", "search", "account"])
        ms = rng.randint(28, 95)
        warm = moment > deploy_done + timedelta(minutes=10) or moment < deploy_done
        miss_chance = 0.1 if warm else 0.6
        cache = "MISS" if rng.random() < miss_chance else "HIT"
        events.append((moment, "web", "INFO GET /{}/{} 200 {}ms cache={}".format(locale, page, ms, cache), None))

    moment = start
    while moment < end:
        moment += timedelta(minutes=3)
        events.append((moment, "healthcheck", "INFO /healthz 200 3ms", None))

    moment = start
    while moment < end:
        moment += timedelta(minutes=10)
        p95 = rng.randint(114, 124)
        events.append((moment, "metrics", "5xx_rate=0.02% p95_latency_ms={}".format(p95), None))

    for hms in ["13:35:20", "13:52:05", "14:20:44", "14:48:10", "15:20:31", "15:55:02", "16:15:47", "16:40:12"]:
        events.append(
            (at(hms), "web", "WARN i18n missing key=footer.legacy_promo locale=en-US fallback=none sampled=1/60s", None)
        )

    for _ in range(9):
        when = start + timedelta(seconds=rng.randint(0, int((end - start).total_seconds())))
        text = rng.choice(
            [
                "WARN slow response path=/api/search ms={}".format(rng.randint(700, 950)),
                "WARN deprecated header X-Legacy-Client seen client=partner-feed",
                "WARN retrying connection pool=catalog attempt=2",
            ]
        )
        events.append((when, "web", text, None))
    return events


def build():
    rng = random.Random(7)
    events = key_events() + noise_events(rng)
    events.sort(key=lambda item: (item[0], item[1]))

    ids = {}
    lines = [
        "INCIDENT LOG",
        "Service: web-frontend (storefront). All times UTC, 2026-10-14.",
        "Everything below is what the on-call engineer can see. Lines are numbered so a brief can cite them.",
        "",
    ]
    for number, (moment, source, message, tag) in enumerate(events, start=1):
        line_id = "L{:03d}".format(number)
        if tag:
            ids[tag] = line_id
        lines.append("{} {} {:<14} {}".format(line_id, stamp(moment), source, message))
    OUT.joinpath("logs.txt").write_text("\n".join(lines) + "\n")
    return ids, len(events)


def write_key(ids):
    warns = [ids["warn_{}".format(n)] for n in range(1, 7)]
    key = {
        "id": "translation_fallback_01",
        "true_cause": (
            "Release 2026.10.14.2 regenerated the static locale files, and keys went missing for "
            "de-DE, fr-FR and ja-JP. The app silently falls back to English for any missing key, "
            "so nothing errors. The missing-key warnings start right after the release and not before."
        ),
        "must_cite_any": warns,
        "must_name_as_cause": ["2026.10.14.2"],
        "release_words": ["release", "deploy"],
        "decoys": [
            {
                "id": "cdn_ttl",
                "why_tempting": "The customer sees wrong content shortly after a CDN cache TTL change, which looks like stale cache.",
                "why_wrong": (
                    "The cache was invalidated at {} and later requests show cache=MISS serving the new "
                    "files. The new files themselves are missing the keys."
                ).format(ids["invalidated"]),
                "lines": [ids["cdn_change"]],
                "keywords": ["cdn", "cache ttl", "ttl", "stale cache", "revalidation"],
            },
            {
                "id": "recs_timeout",
                "why_tempting": "It is the only line that says 'timeout' in the logs, so it reads like a failure.",
                "why_wrong": "One timeout, on a recommendations call, unrelated to text on the page.",
                "lines": [ids["recs_timeout"]],
                "keywords": ["recs-service", "recommendations", "timeout"],
            },
        ],
        "detection_gap": (
            "5xx rate and latency stayed flat, and the only signal was a sampled WARN about falling back "
            "to English. An alert on missing-key or fallback warnings, or a build check that fails when "
            "a locale is missing keys that English has, would have caught this before customers did."
        ),
        "detection_topics": ["translat", "locali", "i18n", "locale", "fallback", "falling back", "falls back", "fall back", "missing key"],
        "detection_actions": ["test", "check", "alert", "validation", "validate", "monitor", "assert"],
    }
    OUT.joinpath("answer_key.json").write_text(json.dumps(key, indent=2) + "\n")


if __name__ == "__main__":
    line_ids, total = build()
    write_key(line_ids)
    print("lines:", total)
    for tag, line_id in sorted(line_ids.items(), key=lambda pair: pair[1]):
        print(line_id, tag)
