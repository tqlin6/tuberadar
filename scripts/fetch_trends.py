"""
TubeRadar – YouTube trend detector.

Fetches popular videos from the YouTube Data API, scores them by momentum
(views per hour since publish, weighted by engagement), then clusters them
by shared keywords to surface emerging topics.

Run locally:   YOUTUBE_API_KEY=xxx python scripts/fetch_trends.py
Run in CI:     handled by .github/workflows/update-trends.yml

Output: data/trends.json
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE = "https://www.googleapis.com/youtube/v3"

# Categories most relevant to content creators looking for video ideas.
# Music is excluded – chart positions are dominated by record labels and
# aren't actionable for individual creators.
CATEGORIES = {
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Tech",
}

# Add the global "most popular" chart on top, untyped.
INCLUDE_GLOBAL = True

REGIONS = os.environ.get("TUBERADAR_REGIONS", "US,GB").split(",")
MAX_PER_CATEGORY = 25     # API max is 50; 25 keeps quota usage low
TOP_TOPICS = 18           # how many trending topics to surface
TOP_VIDEOS = 24           # how many breakout videos to surface

# Words that pollute keyword analysis – they appear on everything.
STOPWORDS = set("""
a an the and or but of for to in on at by with from as is are was were be been being
this that these those it its it's i'm we're you're they're he she them us our your their my
how what why when where who which whose whom about into onto out up down off over
under again further then once here there all any both each few more most other some
such no nor not only own same so than too very can will just don should now
new newest latest official video full part episode ep day days week vs versus
2023 2024 2025 2026 watch ft feat featuring music
ll ve re
""".split())
# Note: kept first-person/second-person pronouns (i, we, you, they) – they anchor
# common hook patterns like "I tried X" and "You won't believe Y" that creators
# actively want to spot.

# ---------------------------------------------------------------------------
# YouTube API
# ---------------------------------------------------------------------------

def api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("ERROR: YOUTUBE_API_KEY not set. See README for setup.")
    return key


def fetch_chart(region: str, category_id: str | None = None) -> list[dict]:
    """Fetch the 'most popular' chart for a region, optionally by category."""
    params = {
        "part": "snippet,statistics,contentDetails",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": MAX_PER_CATEGORY,
        "key": api_key(),
    }
    if category_id:
        params["videoCategoryId"] = category_id

    url = f"{API_BASE}/videos?{urlencode(params)}"
    r = requests.get(url, timeout=20)

    if r.status_code != 200:
        # Some category/region combinations return 404 – that's fine, skip them.
        if r.status_code == 404:
            return []
        print(f"  ! API error {r.status_code} for {region}/{category_id}: {r.text[:200]}")
        return []

    return r.json().get("items", [])


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def hours_since(iso_ts: str) -> float:
    published = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - published
    return max(delta.total_seconds() / 3600, 1.0)


def momentum_score(video: dict) -> float:
    """
    A single number representing how 'hot' a video is.

    Combines view velocity (views/hour) with engagement quality. The log
    smooths the long tail – we don't want a single 50M-view video to dwarf
    everything else, since we care about *emerging* momentum.
    """
    stats = video.get("statistics", {})
    views = int(stats.get("viewCount", 0))
    likes = int(stats.get("likeCount", 0))
    comments = int(stats.get("commentCount", 0))

    age_h = hours_since(video["snippet"]["publishedAt"])
    velocity = views / age_h                                  # views per hour
    engagement = (likes + comments * 5) / max(views, 1)       # 0–1ish

    # log10(velocity) gives a more readable scale; multiply by engagement boost.
    return math.log10(velocity + 1) * (1 + engagement * 2)


def normalize(videos: list[dict]) -> list[dict]:
    """Convert raw API items into the shape the frontend consumes."""
    out = []
    for v in videos:
        sn = v["snippet"]
        st = v.get("statistics", {})
        age_h = hours_since(sn["publishedAt"])
        views = int(st.get("viewCount", 0))

        out.append({
            "id": v["id"],
            "title": sn["title"],
            "channel": sn["channelTitle"],
            "channel_id": sn["channelId"],
            "thumbnail": sn["thumbnails"].get("medium", {}).get("url", ""),
            "published_at": sn["publishedAt"],
            "category_id": sn.get("categoryId"),
            "views": views,
            "likes": int(st.get("likeCount", 0)),
            "comments": int(st.get("commentCount", 0)),
            "age_hours": round(age_h, 1),
            "views_per_hour": round(views / age_h),
            "momentum": round(momentum_score(v), 3),
            "url": f"https://www.youtube.com/watch?v={v['id']}",
        })
    return out


# ---------------------------------------------------------------------------
# Topic clustering
# ---------------------------------------------------------------------------

TOKEN_RE = re.compile(r"[a-z0-9']+")

def tokenize(title: str) -> list[str]:
    title = title.lower()
    # Strip emoji and most non-letter characters.
    tokens = TOKEN_RE.findall(title)
    # Allow 2-letter terms (ai, vr, tv, 5g) since those are real trend signals,
    # but drop pure numbers and stopwords.
    return [
        t for t in tokens
        if t not in STOPWORDS
        and (len(t) >= 2 or t == "i")  # keep "i" so "i tried" / "i built" surface
        and not t.isdigit()
    ]


def ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_topics(videos: list[dict]) -> list[dict]:
    """
    Surface phrases that recur across multiple high-momentum videos.

    A 'topic' is a 1, 2, or 3-word phrase. We score each phrase by:
        sum(momentum) of videos that contain it × frequency boost
    and filter to phrases that appear in at least 2 videos.
    """
    phrase_videos: dict[str, list[dict]] = defaultdict(list)
    phrase_counts: Counter[str] = Counter()

    for v in videos:
        tokens = tokenize(v["title"])
        seen_in_video = set()

        for n in (3, 2, 1):  # prefer longer phrases when they exist
            for phrase in ngrams(tokens, n):
                # Skip phrases that are just a single stopword-adjacent term.
                if len(phrase) < 4:
                    continue
                if phrase in seen_in_video:
                    continue
                seen_in_video.add(phrase)
                phrase_videos[phrase].append(v)
                phrase_counts[phrase] += 1

    topics = []
    for phrase, vids in phrase_videos.items():
        if len(vids) < 2:
            continue  # need at least 2 videos to count as a "trend"

        # Skip phrases fully contained in a more popular longer phrase –
        # avoids "minecraft" duplicating "minecraft hardcore".
        is_subsumed = any(
            phrase != other
            and phrase in other
            and phrase_counts[other] >= phrase_counts[phrase]
            for other in phrase_counts
        )
        if is_subsumed:
            continue

        total_momentum = sum(v["momentum"] for v in vids)
        topics.append({
            "phrase": phrase,
            "video_count": len(vids),
            "momentum": round(total_momentum, 2),
            "example_videos": [
                {"id": v["id"], "title": v["title"], "channel": v["channel"],
                 "thumbnail": v["thumbnail"], "url": v["url"],
                 "views": v["views"], "age_hours": v["age_hours"]}
                for v in sorted(vids, key=lambda x: x["momentum"], reverse=True)[:3]
            ],
        })

    topics.sort(key=lambda t: t["momentum"], reverse=True)
    return topics[:TOP_TOPICS]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> None:
    all_videos: dict[str, dict] = {}  # dedupe by video id across categories

    for region in REGIONS:
        region = region.strip().upper()
        print(f"Fetching region: {region}")

        sources = []
        if INCLUDE_GLOBAL:
            sources.append((None, "Global"))
        sources.extend(CATEGORIES.items())

        for cat_id, cat_name in sources:
            items = fetch_chart(region, cat_id)
            print(f"  {cat_name:18} → {len(items):2} videos")
            for v in normalize(items):
                v["region"] = region
                v["category"] = CATEGORIES.get(v.get("category_id"), "Other")
                # Keep the version with highest momentum if seen in multiple charts.
                existing = all_videos.get(v["id"])
                if not existing or v["momentum"] > existing["momentum"]:
                    all_videos[v["id"]] = v

    videos = sorted(all_videos.values(), key=lambda v: v["momentum"], reverse=True)
    print(f"\nTotal unique videos: {len(videos)}")

    topics = extract_topics(videos)
    print(f"Trending topics found: {len(topics)}")

    # Build category breakdown – useful for the frontend filter.
    by_category: Counter[str] = Counter()
    for v in videos:
        by_category[v["category"]] += 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regions": REGIONS,
        "stats": {
            "total_videos": len(videos),
            "total_topics": len(topics),
            "by_category": dict(by_category),
        },
        "topics": topics,
        "breakout_videos": videos[:TOP_VIDEOS],
    }

    out_path = Path(__file__).resolve().parent.parent / "data" / "trends.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    run()
