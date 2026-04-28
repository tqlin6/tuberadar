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

REGIONS = os.environ.get(
    "TUBERADAR_REGIONS",
    "US,GB,CA,AU,IN,DE,BR"
).split(",")

# Human-readable region names for the UI.
REGION_NAMES = {
    "US": "United States",
    "GB": "United Kingdom",
    "CA": "Canada",
    "AU": "Australia",
    "IN": "India",
    "DE": "Germany",
    "BR": "Brazil",
    "FR": "France",
    "JP": "Japan",
    "MX": "Mexico",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "ID": "Indonesia",
    "PH": "Philippines",
}

MAX_PER_CATEGORY = 15     # reduced from 25 to fit more regions in quota
TOP_TOPICS = 18           # how many trending topics to surface
TOP_VIDEOS = 24           # how many breakout videos to surface

# ---- Emerging themes (zeitgeist detection) ----
# Looks for phrases that lots of *different* creators have started uploading
# about in a short window – the signal of a topic catching fire across YouTube,
# not a single big channel posting.
THEME_WINDOW_HOURS = 12          # how recent uploads must be
THEME_MAX_SUBSCRIBERS = 1_000_000  # exclude channels above this size
THEME_MIN_CHANNELS = 5           # need uploads from at least this many distinct channels
THEME_MIN_VIDEOS = 8             # and at least this many recent videos
THEME_CANDIDATES = 8             # how many candidate phrases to validate (quota controller)
THEME_SEARCH_RESULTS = 30        # videos fetched per phrase via search.list
TOP_THEMES = 12                  # how many themes to surface in the output

# ---------------------------------------------------------------------------
# Multilingual stopword and vocabulary lists
# ---------------------------------------------------------------------------
# A 'topic' in any language is a phrase that's specific and substantive.
# To find those, we need to filter out (a) stopwords (the/and/of equivalents)
# and (b) YouTube vocabulary (their version of "shorts/funny/edit/best").
#
# Each supported language has its own pair of lists. Title language is
# detected per video so a Brazilian Portuguese title gets the Portuguese
# filter, an English title gets the English filter, etc.
#
# Honest limitations:
# - Hindi/Devanagari script videos won't tokenize (Latin-only tokenizer).
#   Indian English content surfaces; pure Hindi script videos are invisible.
# - Spanish vs Portuguese detection is imperfect for short titles - they
#   share many words. We use region as a tiebreaker (BR=pt, ES/MX=es).

LANG_STOPWORDS = {
    "en": set("""
a an the and or but of for to in on at by with from as is are was were be been being
this that these those it its it's i'm we're you're they're he she them us our your their my
how what why when where who which whose whom about into onto out up down off over
under again further then once here there all any both each few more most other some
such no nor not only own same so than too very can will just don should now
new newest latest full part episode ep day days week vs versus
2023 2024 2025 2026 watch ft feat featuring
ll ve re
""".split()),

    "pt": set("""
a o as os um uma uns umas de do da dos das e ou mas em no na nos nas
para por com sem sob sobre entre ate até desde
que quem qual quais quando onde como porque
eu tu ele ela nos nós vos vós eles elas voce você voces vocês
me te se lhe nos vos lhes meu minha teu tua seu sua nosso nossa vosso vossa
isto isso aquilo este esta esse essa aquele aquela
ja já ainda apenas só somente também tambem nao não sim
mais menos muito muita muitos muitas pouco pouca poucos poucas
ser estar ter haver fazer ir vir dar ver dizer poder querer dever saber
foi era sou sao são fui fomos serao serão tem têm tinha tem teve
hoje ontem amanha amanhã agora depois antes sempre nunca
ep episodio episódio dia dias semana mes mês ano anos parte completo full
""".split()),

    "de": set("""
der die das den dem des ein eine einen einer eines einem
und oder aber doch denn weil wenn dass ob als wie
ich du er sie es wir ihr mich mir dich dir ihn ihm uns euch
mein meine dein deine sein seine unser unsere euer eure
in auf an bei zu mit von vor nach aus über unter neben hinter
durch gegen ohne um für trotz
ist sind war waren bin bist sein sei werden wird wurde geworden
hat haben habe hatte gehabt
nicht kein keine keinen keiner keines keinem
ja nein doch nur auch noch schon mehr weniger viel viele
heute gestern morgen jetzt dann immer nie
neu neue alt alte voll teil tag tage woche monat jahr
ep episode folge teil
""".split()),

    "es": set("""
el la los las un una unos unas
de del al en con sin sobre entre hasta desde
y o pero porque si que cual cuales quien quienes cuando donde como
yo tu él ella nosotros vosotros ellos ellas usted ustedes
me te se nos os le les lo la
mi mis tu tus su sus nuestro nuestra vuestro vuestra
ser estar tener haber hacer ir venir dar ver decir poder querer
es son era fue fueron fui estoy esta están está
no si también tambien aún ya solo
mas menos muy mucho muchos pocos
hoy ayer mañana ahora antes después siempre nunca
nuevo viejo lleno parte
""".split()),
}

LANG_YOUTUBE_VOCAB = {
    "en": set("""
shorts short reel reels clip clips video videos movie movies film films
funny lol haha cringe hilarious wild crazy insane unbelievable shocking
game gaming gameplay playthrough walkthrough speedrun stream livestream
edit edits edited editing montage compilation highlights highlight
review reviews reacting reaction reactions react reacts unboxing
tutorial guide tips tricks hacks how-to howto explained explainer
top best worst greatest ultimate every all-time
official music song songs lyrics audio
channel subscribe subscriber subscribers like comment share
youtube tiktok instagram twitter
content creator creators
asmr vlog vlogs blog blogs podcast podcasts interview interviews
trailer trailers teaser teasers preview
behind scenes bts
youtubeshorts shortsvideo shortsfeed viralshorts trendingshorts
viralvideo viral trending trendy fyp foryou foryoupage
prank pranks comedy relatable mood vibe vibes daily
new latest live update updates
""".split()),

    "pt": set("""
shorts video videos clipe clipes filme filmes
engraçado engracado louco louca incrivel incrível chocante
jogo jogos gameplay
edicao edição edicoes edições montagem
review reviews reagindo reacao reação reagao
tutorial guia dicas truques
top melhor pior melhores piores
oficial musica música cancao canção
canal inscrevase inscreve-se inscritos curtir comentar compartilhar
youtube tiktok instagram
conteudo conteúdo criador criadores
vlog vlogs podcast podcasts entrevista entrevistas
trailer teaser
""".split()),

    "de": set("""
shorts video videos clip clips film filme
lustig witzig verrückt verrueckt krass unglaublich
spiel spiele gaming
schnitt schnitten zusammenschnitt
review reviews reaktion reaktionen reagiere
tutorial anleitung tipps tricks
top beste schlechteste großte größte
offiziell musik lied lieder
kanal abonniere abonnenten abo
youtube tiktok instagram
inhalt ersteller
vlog vlogs podcast interview interviews
trailer teaser
""".split()),

    "es": set("""
shorts video videos clip clips pelicula película
divertido gracioso loco increible increíble
juego juegos
edicion edición montaje
review reviews reaccion reacción reaccionando
tutorial guia guía consejos trucos
top mejor peor
oficial musica música cancion canción
canal suscribete suscríbete suscriptores
youtube tiktok instagram
contenido creador creadores
vlog vlogs podcast entrevista
trailer
""".split()),
}

# Region → likely primary language. Used as a hint for ambiguous detection.
REGION_LANG_HINT = {
    "US": "en", "GB": "en", "CA": "en", "AU": "en", "IN": "en",
    "DE": "de",
    "BR": "pt",
    "ES": "es", "MX": "es",
    "FR": "fr", "JP": "ja", "IT": "it", "NL": "nl",
    "ID": "id", "PH": "en",
}

# Backwards-compatibility shims: parts of the script still reference the old
# flat STOPWORDS/YOUTUBE_VOCAB sets (e.g. tokenizer fallback). Point them at
# the English versions, which is what they were before.
STOPWORDS = LANG_STOPWORDS["en"]
YOUTUBE_VOCAB = LANG_YOUTUBE_VOCAB["en"]


def detect_title_language(title: str, region_hint: str | None = None) -> str:
    """
    Best-effort title language detection. Returns one of the language codes
    in LANG_STOPWORDS, or 'en' as a safe fallback.

    Strategy: count how many words in the title appear in each language's
    stopword list. Whichever language wins gets it. Region hint nudges the
    tiebreaker for ambiguous short titles.
    """
    if not title:
        return "en"

    # Tokenize loosely - just lowercase letters, no language-specific chars yet.
    words = re.findall(r"[a-záéíóúâêîôûãõàèìòùäöüçñ']+", title.lower())
    if not words:
        return "en"

    # If most characters aren't Latin letters at all, skip - this is e.g.
    # Devanagari, Cyrillic, CJK. Return 'en' as a safe default; the topic
    # extractor will then likely filter out most/all of the tokens anyway.
    latin_chars = sum(1 for c in title if c.isalpha() and ord(c) < 0x80)
    total_chars = sum(1 for c in title if c.isalpha())
    if total_chars > 0 and latin_chars / total_chars < 0.5:
        return REGION_LANG_HINT.get(region_hint or "", "en")

    scores: dict[str, int] = {}
    for lang, stopwords in LANG_STOPWORDS.items():
        scores[lang] = sum(1 for w in words if w in stopwords)

    # Threshold: need at least 1 stopword match to claim a language.
    best_lang = max(scores, key=scores.get)
    if scores[best_lang] == 0:
        # No stopwords matched any language. Fall back to region hint.
        return REGION_LANG_HINT.get(region_hint or "", "en")

    # If tie between two languages, prefer the region hint.
    top_score = scores[best_lang]
    tied = [lang for lang, score in scores.items() if score == top_score]
    if len(tied) > 1 and region_hint:
        hint = REGION_LANG_HINT.get(region_hint, "en")
        if hint in tied:
            return hint

    return best_lang


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# YouTube API
# ---------------------------------------------------------------------------

def api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("ERROR: YOUTUBE_API_KEY not set. See README for setup.")
    return key


# Global flag: once we hit a quota-exceeded error, stop attempting API calls.
# YouTube quota resets at midnight Pacific time. Continuing to call the API
# after hitting the limit just wastes time and pollutes logs.
_QUOTA_EXHAUSTED = False


def _is_quota_error(response: requests.Response) -> bool:
    """Detect YouTube's 'quota exceeded' error so we can short-circuit."""
    if response.status_code != 403:
        return False
    try:
        body = response.json()
        for err in body.get("error", {}).get("errors", []):
            if err.get("reason") in ("quotaExceeded", "rateLimitExceeded"):
                return True
        # Fallback: check the message text.
        msg = body.get("error", {}).get("message", "").lower()
        return "quota" in msg
    except Exception:
        return "quota" in response.text.lower()


def fetch_chart(region: str, category_id: str | None = None) -> list[dict]:
    """Fetch the 'most popular' chart for a region, optionally by category."""
    global _QUOTA_EXHAUSTED
    if _QUOTA_EXHAUSTED:
        return []

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
        if _is_quota_error(r):
            _QUOTA_EXHAUSTED = True
            print(f"  ✗ Quota exhausted at {region}/{category_id}. "
                  f"Stopping further API calls.")
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

TOKEN_RE = re.compile(r"[a-z0-9'áéíóúâêîôûãõàèìòùäöüçñ]+")

def tokenize(title: str, lang: str = "en") -> list[str]:
    """Lowercase, strip non-letters, remove stopwords for the given language."""
    title = title.lower()
    tokens = TOKEN_RE.findall(title)
    stopwords = LANG_STOPWORDS.get(lang, LANG_STOPWORDS["en"])
    return [
        t for t in tokens
        if t not in stopwords
        and (len(t) >= 2 or t == "i")
        and not t.isdigit()
    ]


def ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_topics(videos: list[dict], lang: str = "en") -> list[dict]:
    """
    Surface phrases that recur across multiple high-momentum videos.

    Operates in a single language at a time - the caller groups videos by
    detected language first, then calls this with the relevant lang code.
    Stopwords and YouTube vocabulary are looked up for that language.
    """
    if not videos:
        return []

    vocab = LANG_YOUTUBE_VOCAB.get(lang, LANG_YOUTUBE_VOCAB["en"])

    phrase_videos: dict[str, list[dict]] = defaultdict(list)
    phrase_counts: Counter[str] = Counter()

    for v in videos:
        tokens = tokenize(v["title"], lang=lang)
        seen_in_video = set()

        for n in (3, 2, 1):
            for phrase in ngrams(tokens, n):
                if len(phrase) < 4:
                    continue
                if phrase in seen_in_video:
                    continue
                seen_in_video.add(phrase)
                phrase_videos[phrase].append(v)
                phrase_counts[phrase] += 1

    total_videos = len(videos)
    topics = []

    for phrase, vids in phrase_videos.items():
        if len(vids) < 2:
            continue

        words = phrase.split()

        if len(words) == 1:
            word = words[0]
            if word in vocab:
                continue
            if len(vids) / total_videos > 0.15:
                continue
            if len(vids) < 4:
                continue
        elif all(w in vocab for w in words):
            continue

        is_subsumed = any(
            phrase != other
            and phrase in other
            and phrase_counts[other] >= phrase_counts[phrase]
            for other in phrase_counts
        )
        if is_subsumed:
            continue

        word_count_bonus = 1.0 + 0.25 * (len(words) - 1)
        total_momentum = sum(v["momentum"] for v in vids) * word_count_bonus

        regions_seen = sorted({v.get("region", "??") for v in vids})

        topics.append({
            "phrase": phrase,
            "video_count": len(vids),
            "momentum": round(total_momentum, 2),
            "regions": regions_seen,
            "lang": lang,
            "example_videos": [
                {"id": v["id"], "title": v["title"], "channel": v["channel"],
                 "thumbnail": v["thumbnail"], "url": v["url"],
                 "views": v["views"], "age_hours": v["age_hours"]}
                for v in sorted(vids, key=lambda x: x["momentum"], reverse=True)[:3]
            ],
        })

    topics.sort(key=lambda t: t["momentum"], reverse=True)
    return topics[:TOP_TOPICS]


def extract_topics_per_region(videos: list[dict]) -> dict[str, list[dict]]:
    """
    Compute topics independently for each region, using each video's
    detected language for filtering.

    Returns: dict mapping region code -> list of topics for that region.
    The special key "ALL" gets a globally merged topic list (English-only,
    since cross-language merging produces noise).
    """
    by_region: dict[str, list[dict]] = defaultdict(list)
    for v in videos:
        region = v.get("region")
        if region:
            by_region[region].append(v)

    topics_by_region: dict[str, list[dict]] = {}

    for region, region_videos in by_region.items():
        # Group this region's videos by detected language so each language
        # gets its own filtering pass.
        by_lang: dict[str, list[dict]] = defaultdict(list)
        for v in region_videos:
            lang = detect_title_language(v["title"], region_hint=region)
            v["_detected_lang"] = lang  # cache for later
            by_lang[lang].append(v)

        # Extract topics per language, then merge by momentum within the region.
        all_region_topics = []
        for lang, lang_videos in by_lang.items():
            all_region_topics.extend(extract_topics(lang_videos, lang=lang))

        all_region_topics.sort(key=lambda t: t["momentum"], reverse=True)
        topics_by_region[region] = all_region_topics[:TOP_TOPICS]
        print(f"  {region}: {len(all_region_topics)} topics across "
              f"{len(by_lang)} language(s) "
              f"({', '.join(f'{l}={len(vs)}' for l, vs in by_lang.items())})")

    # Build a global "ALL" view: take all English topics across all regions
    # plus the top per-region non-English topic. This avoids the previous
    # behaviour where "all" was dominated by US/GB content.
    all_topics: list[dict] = []
    for topics in topics_by_region.values():
        all_topics.extend(topics)
    # Dedupe by phrase, keeping highest-momentum version.
    seen: dict[str, dict] = {}
    for t in all_topics:
        if t["phrase"] not in seen or t["momentum"] > seen[t["phrase"]]["momentum"]:
            seen[t["phrase"]] = t
    merged = sorted(seen.values(), key=lambda t: t["momentum"], reverse=True)
    topics_by_region["ALL"] = merged[:TOP_TOPICS]

    return topics_by_region


# ---------------------------------------------------------------------------
# Emerging themes (zeitgeist detection)
# ---------------------------------------------------------------------------

def search_recent_uploads(query: str, hours: int = THEME_WINDOW_HOURS,
                          max_results: int = THEME_SEARCH_RESULTS) -> list[dict]:
    """Find videos uploaded in the last `hours` whose title contains `query`."""
    global _QUOTA_EXHAUSTED
    if _QUOTA_EXHAUSTED:
        return []

    published_after = datetime.now(timezone.utc).timestamp() - hours * 3600
    published_after_iso = datetime.fromtimestamp(
        published_after, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "order": "date",
        "publishedAfter": published_after_iso,
        "maxResults": max_results,
        "key": api_key(),
    }
    url = f"{API_BASE}/search?{urlencode(params)}"
    r = requests.get(url, timeout=20)
    if r.status_code != 200:
        if _is_quota_error(r):
            _QUOTA_EXHAUSTED = True
            print(f"  ✗ Quota exhausted during theme validation. Stopping.")
            return []
        print(f"  ! search error {r.status_code} for '{query}': {r.text[:150]}")
        return []
    return r.json().get("items", [])


def fetch_channel_subscriber_counts(channel_ids: list[str]) -> dict[str, int]:
    """
    Look up subscriber counts for a batch of channels.
    The channels.list endpoint accepts up to 50 IDs per call.
    """
    global _QUOTA_EXHAUSTED
    counts: dict[str, int] = {}
    if not channel_ids or _QUOTA_EXHAUSTED:
        return counts

    # De-dupe and chunk into 50s.
    unique_ids = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique_ids), 50):
        if _QUOTA_EXHAUSTED:
            break
        chunk = unique_ids[i:i + 50]
        params = {
            "part": "statistics",
            "id": ",".join(chunk),
            "key": api_key(),
        }
        url = f"{API_BASE}/channels?{urlencode(params)}"
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            if _is_quota_error(r):
                _QUOTA_EXHAUSTED = True
                print(f"  ✗ Quota exhausted fetching channel data.")
                break
            print(f"  ! channels error {r.status_code}: {r.text[:150]}")
            continue
        for item in r.json().get("items", []):
            stats = item.get("statistics", {})
            # Some channels hide their subscriber count – treat as 0 (small).
            if stats.get("hiddenSubscriberCount"):
                counts[item["id"]] = 0
            else:
                counts[item["id"]] = int(stats.get("subscriberCount", 0))
    return counts


def is_valid_theme_candidate(phrase: str) -> bool:
    """
    Themes must be specific, descriptive phrases — not generic vocabulary.
    Single words like 'baby', 'life', 'travel' have plenty of search volume
    but aren't actionable themes; they're too broad to mean anything.
    Hook-style phrases like 'i tried' aren't themes either — they're formats.
    """
    words = phrase.split()
    # Rule 1: Must be multi-word.
    if len(words) < 2:
        return False
    # Rule 2: Reject phrases made entirely of YouTube vocabulary.
    if all(w in YOUTUBE_VOCAB for w in words):
        return False
    # Rule 3: Reject hook formulas (typically pronoun + short verb).
    # If the average word length is under 4 chars, it's probably a hook
    # ("i tried", "we made", "you won") rather than a substantive subject.
    avg_word_len = sum(len(w) for w in words) / len(words)
    if avg_word_len < 4:
        return False
    # Rule 4: Reject if any word is a pronoun – pronouns belong in topics
    # (as hooks), not themes (as subjects).
    PRONOUNS = {"i", "we", "you", "they", "he", "she", "it"}
    if any(w in PRONOUNS for w in words):
        return False
    return True


def extract_emerging_themes(candidate_phrases: list[str]) -> list[dict]:
    """
    For each candidate phrase, find recent uploads via search.list and
    determine whether it qualifies as an 'emerging theme':
      - At least THEME_MIN_VIDEOS uploads in the last THEME_WINDOW_HOURS
      - From at least THEME_MIN_CHANNELS distinct channels
      - With most uploads coming from sub-THEME_MAX_SUBSCRIBERS channels
        (so a single big creator can't anoint a phrase as 'trending')
    """
    # First pass: only keep candidates that look like real themes.
    # Single words ("baby", "life") and hooks ("i tried") get rejected here.
    valid_candidates = [p for p in candidate_phrases if is_valid_theme_candidate(p)]
    rejected_count = len(candidate_phrases) - len(valid_candidates)
    if rejected_count:
        print(f"  (rejected {rejected_count} non-theme candidate(s) before validation)")

    themes = []
    cutoff_ts = datetime.now(timezone.utc).timestamp() - THEME_WINDOW_HOURS * 3600

    for phrase in valid_candidates[:THEME_CANDIDATES]:
        items = search_recent_uploads(phrase)
        if len(items) < THEME_MIN_VIDEOS:
            continue

        # Collect channel IDs to look up subscriber counts in one batch.
        channel_ids = [it["snippet"]["channelId"] for it in items]
        sub_counts = fetch_channel_subscriber_counts(channel_ids)

        # Filter to videos from sub-cap channels.
        small_creator_videos = []
        all_channels = set()
        for it in items:
            sn = it["snippet"]
            ch_id = sn["channelId"]
            all_channels.add(ch_id)
            sub_count = sub_counts.get(ch_id, 0)
            if sub_count > THEME_MAX_SUBSCRIBERS:
                continue
            published = datetime.fromisoformat(
                sn["publishedAt"].replace("Z", "+00:00")
            ).timestamp()
            if published < cutoff_ts:
                continue  # double-check freshness; API can be lenient
            small_creator_videos.append({
                "id": it["id"]["videoId"],
                "title": sn["title"],
                "channel": sn["channelTitle"],
                "channel_id": ch_id,
                "subscribers": sub_count,
                "thumbnail": sn["thumbnails"].get("medium", {}).get("url", ""),
                "published_at": sn["publishedAt"],
                "url": f"https://www.youtube.com/watch?v={it['id']['videoId']}",
            })

        small_creator_channels = {v["channel_id"] for v in small_creator_videos}

        # Apply the qualification thresholds.
        if len(small_creator_videos) < THEME_MIN_VIDEOS:
            continue
        if len(small_creator_channels) < THEME_MIN_CHANNELS:
            continue

        # Compute upload velocity: videos per hour from distinct channels,
        # since a single channel posting 5 videos shouldn't count 5x.
        velocity = len(small_creator_channels) / THEME_WINDOW_HOURS

        # Sort example videos by recency for display.
        small_creator_videos.sort(key=lambda v: v["published_at"], reverse=True)

        themes.append({
            "phrase": phrase,
            "video_count": len(small_creator_videos),
            "channel_count": len(small_creator_channels),
            "total_channels_seen": len(all_channels),
            "uploads_per_hour": round(velocity, 2),
            "window_hours": THEME_WINDOW_HOURS,
            "example_videos": small_creator_videos[:4],
        })
        print(f"  ✓ '{phrase}' → {len(small_creator_videos)} videos / "
              f"{len(small_creator_channels)} channels")

    # Rank by channel diversity first, then total volume – a phrase covered
    # by 20 different small creators beats one covered by 30 videos from 8.
    themes.sort(
        key=lambda t: (t["channel_count"], t["video_count"]),
        reverse=True,
    )
    return themes[:TOP_THEMES]



# ---------------------------------------------------------------------------
# Trending search terms (via YouTube autocomplete)
# ---------------------------------------------------------------------------
# YouTube's autocomplete endpoint returns the most popular completions for
# any search prefix. By tracking which completions appear today that weren't
# there in previous runs, we identify what people are starting to search for –
# a leading indicator of emerging interest, complementing the upload-side
# signals from the popular charts.
#
# This endpoint is separate from the Data API and doesn't count toward our
# 10K/day quota. It's effectively unlimited (within reasonable rate limits).

import json as _json_mod  # alias to avoid shadowing in jsonp parsing

# Seed prefixes to query. These are deliberately broad – the autocomplete
# results give us the current top completions, which is the actual trend signal.
SEARCH_SEED_PREFIXES = [
    "how to", "how do", "how does",
    "why is", "why do", "why does",
    "what is", "what are", "what happened",
    "best", "worst", "top",
    "is it", "should i",
    "can you",
]

TOP_SEARCH_TERMS = 12   # how many search trends to surface


def fetch_youtube_autocomplete(prefix: str, region: str = "US") -> list[str]:
    """Hit YouTube's autocomplete endpoint for a given prefix."""
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "client": "youtube",
        "ds": "yt",
        "q": prefix,
        "hl": "en",
        "gl": region.lower(),
    }
    try:
        r = requests.get(f"{url}?{urlencode(params)}", timeout=10)
        if r.status_code != 200:
            return []
        # Response is JSONP-ish: window.google.ac.h([...]) – strip the wrapper.
        text = r.text.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []
        parsed = _json_mod.loads(text[start:end + 1])
        # Structure: [prefix, [[suggestion, 0], [suggestion, 0], ...], ...]
        if len(parsed) < 2 or not isinstance(parsed[1], list):
            return []
        return [
            entry[0] for entry in parsed[1]
            if isinstance(entry, list) and len(entry) >= 1
            and isinstance(entry[0], str)
        ]
    except Exception as e:
        print(f"  ! autocomplete error for '{prefix}': {e}")
        return []


def collect_trending_searches(prev_search_terms: dict[str, str]) -> list[dict]:
    """
    Pull autocomplete suggestions for all seed prefixes and return the ones
    that look 'fresh' – appearing in the top suggestions today.

    For each surfaced term, we record:
      - phrase: the autocompleted suggestion
      - prefix: which seed prefix produced it
      - rank: position in the autocomplete list (1 = top)
      - first_seen_at: when this term first appeared in our tracking
      - is_new: whether this is the first run we've seen it
    """
    results: dict[str, dict] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    for prefix in SEARCH_SEED_PREFIXES:
        suggestions = fetch_youtube_autocomplete(prefix)
        for rank, suggestion in enumerate(suggestions[:10], start=1):
            # Skip if the suggestion is just the prefix itself.
            if suggestion.strip().lower() == prefix.lower():
                continue
            # Keep the highest-ranked appearance of each term.
            if suggestion in results and results[suggestion]["rank"] <= rank:
                continue
            first_seen = prev_search_terms.get(suggestion, now_iso)
            results[suggestion] = {
                "phrase": suggestion,
                "prefix": prefix,
                "rank": rank,
                "first_seen_at": first_seen,
                "is_new": suggestion not in prev_search_terms,
            }
        print(f"  '{prefix}' → {len(suggestions)} suggestions")

    # Sort: new ones first, then by rank.
    sorted_results = sorted(
        results.values(),
        key=lambda x: (not x["is_new"], x["rank"])
    )
    return sorted_results[:TOP_SEARCH_TERMS]


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

    # If we got no videos at all, the API was down or quota was exhausted.
    # Do NOT overwrite the existing trends.json with an empty result – that
    # would wipe a working site. Just exit and leave the previous data alone.
    out_path = Path(__file__).resolve().parent.parent / "data" / "trends.json"
    if not videos:
        if _QUOTA_EXHAUSTED:
            print("✗ No data fetched — YouTube API quota exhausted.")
        else:
            print("✗ No data fetched — API returned no videos.")
        if out_path.exists():
            print(f"  Keeping previous data at {out_path} (last modified: "
                  f"{datetime.fromtimestamp(out_path.stat().st_mtime, tz=timezone.utc).isoformat()}).")
            print("  Site remains live with last successful fetch's data.")
        sys.exit(0)  # Exit cleanly so workflow doesn't show as failed.

    print("\nExtracting topics per region...")
    topics_by_region = extract_topics_per_region(videos)
    topics = topics_by_region.get("ALL", [])
    print(f"Trending topics (all regions, deduped): {len(topics)}")

    # Build a wider candidate pool for theme validation. Themes need
    # multi-word, descriptive phrases — those don't always survive the
    # topic-list cut, so we pull from all regional topic lists, prefer
    # multi-word phrases, and dedupe.
    print(f"\nValidating emerging themes (window: {THEME_WINDOW_HOURS}h, "
          f"sub cap: {THEME_MAX_SUBSCRIBERS:,})...")
    candidate_pool: dict[str, float] = {}
    for region_topics in topics_by_region.values():
        for t in region_topics:
            phrase = t["phrase"]
            momentum = t.get("momentum", 0)
            if len(phrase.split()) < 2:
                continue
            if phrase not in candidate_pool or momentum > candidate_pool[phrase]:
                candidate_pool[phrase] = momentum
    candidate_phrases = sorted(
        candidate_pool.keys(),
        key=lambda p: candidate_pool[p],
        reverse=True
    )
    print(f"  Candidate pool: {len(candidate_phrases)} multi-word phrases")
    themes = extract_emerging_themes(candidate_phrases)
    print(f"Emerging themes confirmed: {len(themes)}")

    # ---- Merge with previous run to preserve "first detected" timestamps ----
    # We read the existing trends.json (if it exists) and look up each theme.
    # If a theme appeared in the previous run, we keep its original
    # first_detected_at. Otherwise it's brand new and gets the current time.
    now_iso = datetime.now(timezone.utc).isoformat()
    previous_first_detected: dict[str, str] = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text())
            for prev_theme in previous.get("emerging_themes", []):
                if "first_detected_at" in prev_theme:
                    previous_first_detected[prev_theme["phrase"]] = prev_theme["first_detected_at"]
        except Exception as e:
            print(f"  (couldn't read previous trends.json: {e})")

    fresh_count = 0
    for theme in themes:
        if theme["phrase"] in previous_first_detected:
            theme["first_detected_at"] = previous_first_detected[theme["phrase"]]
        else:
            theme["first_detected_at"] = now_iso
            fresh_count += 1
        theme["last_seen_at"] = now_iso
    print(f"  → {fresh_count} brand new theme(s), {len(themes) - fresh_count} continuing from previous run")

    # ---- Trending search terms (via YouTube autocomplete) ----
    print(f"\nCollecting trending search terms via autocomplete...")
    # Carry forward first_seen_at timestamps from previous run so we can mark
    # genuinely new terms vs ones that have been around.
    prev_search_terms: dict[str, str] = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text())
            for prev in previous.get("trending_searches", []):
                if "first_seen_at" in prev:
                    prev_search_terms[prev["phrase"]] = prev["first_seen_at"]
        except Exception:
            pass
    trending_searches = collect_trending_searches(prev_search_terms)
    new_searches = sum(1 for s in trending_searches if s.get("is_new"))
    print(f"Trending searches collected: {len(trending_searches)} ({new_searches} new)")

    # Build category breakdown – useful for the frontend filter.
    by_category: Counter[str] = Counter()
    for v in videos:
        by_category[v["category"]] += 1

    output = {
        "generated_at": now_iso,
        "regions": REGIONS,
        "regions_meta": [
            {"code": r.strip().upper(), "name": REGION_NAMES.get(r.strip().upper(), r.strip().upper())}
            for r in REGIONS
        ],
        "stats": {
            "total_videos": len(videos),
            "total_topics": len(topics),
            "total_themes": len(themes),
            "total_searches": len(trending_searches),
            "by_category": dict(by_category),
        },
        "emerging_themes": themes,
        "topics": topics,
        "topics_by_region": topics_by_region,
        "trending_searches": trending_searches,
        "breakout_videos": videos[:TOP_VIDEOS],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    run()
