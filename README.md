# TubeRadar

> A signal feed of emerging YouTube topics for content creators. Updated every six hours.

TubeRadar identifies phrases that are recurring across high-momentum YouTube videos right now — so you can clone the topic before saturation hits. The site is a static HTML/CSS/JS page; the data is refreshed by a Python script that runs on GitHub Actions and writes a JSON file back into the repo.

**Total cost to run: $0/month.**

---

## How it works

```
   ┌────────────────────────┐         ┌──────────────────────┐
   │  GitHub Actions cron   │ ──run── │ scripts/fetch_trends │
   │  (every 6 hours)       │         │      .py             │
   └────────────────────────┘         └──────────┬───────────┘
                                                 │ writes
                                                 ▼
                                       ┌──────────────────────┐
                                       │  data/trends.json    │
                                       └──────────┬───────────┘
                                                  │ committed back
                                                  ▼
                                       ┌──────────────────────┐
                                       │  GitHub Pages        │
                                       │  serves index.html   │
                                       │  + app.js fetches    │
                                       │  the JSON            │
                                       └──────────────────────┘
```

1. The Python script calls the **YouTube Data API v3** (`videos.list?chart=mostPopular`) for several content-creator-relevant categories across the regions you configure.
2. For every video it computes a **momentum score** — a log-smoothed view-velocity (views/hour since publish), weighted by engagement.
3. It tokenizes every title, extracts 1–3 word phrases, drops stopwords, and identifies phrases that appear across multiple high-momentum videos. Those are your trending topics.
4. The result is dumped to `data/trends.json` and committed back to the repo.
5. **GitHub Pages** serves the static site. The frontend `fetch()`es the JSON and renders it.

---

## Deploy in ~10 minutes

### 1. Get a YouTube Data API key (free)

1. Go to <https://console.cloud.google.com/>.
2. Create a new project (any name).
3. Open **APIs & Services → Library**, search **"YouTube Data API v3"**, click **Enable**.
4. Open **APIs & Services → Credentials**, click **Create credentials → API key**.
5. Copy the key. Keep it somewhere safe.

The free tier is 10,000 quota units/day. TubeRadar uses ~30 units per fetch × 4 fetches/day = ~120/day. You have enormous headroom.

### 2. Push this code to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/tuberadar.git
git push -u origin main
```

### 3. Add the API key as a repo secret

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**.
3. Name: `YOUTUBE_API_KEY`. Value: the key from step 1. Save.

(Optional) On the same page, click the **Variables** tab and add `TUBERADAR_REGIONS` with a comma-separated list like `US,GB,CA,AU` to broaden coverage. Default is `US,GB`.

### 4. Turn on GitHub Pages

1. **Settings → Pages**.
2. Under **Source**, select **Deploy from a branch**.
3. Branch: `main`, folder: `/ (root)`. Save.
4. Wait ~30 seconds. Your site will be live at `https://YOUR-USERNAME.github.io/tuberadar/`.

### 5. Trigger the first fetch

The cron only runs at scheduled times, but you can kick it off manually:

1. Go to the **Actions** tab.
2. Click **Update trends** in the sidebar.
3. Click **Run workflow → Run workflow**.

After ~30 seconds the action should complete and commit a fresh `data/trends.json`. Reload your site — it'll show real data.

---

## Customizing

### Change which categories get fetched

Edit the `CATEGORIES` dict at the top of `scripts/fetch_trends.py`. The keys are YouTube's [video category IDs](https://developers.google.com/youtube/v3/docs/videoCategories/list).

### Change which countries get fetched

Set the `TUBERADAR_REGIONS` repository variable to a comma-separated list of [ISO 3166-1 alpha-2 codes](https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes) (e.g. `US,GB,CA,AU,DE,IN`).

### Change the update frequency

Edit the `cron:` line in `.github/workflows/update-trends.yml`. Default is `0 */6 * * *` (every 6 hours). Going more frequent than every 2 hours starts to eat noticeable Actions minutes — be aware of the [free-tier 2,000 minutes/month](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions) limit on private repos. Public repos are unlimited.

### Change how trending is defined

Two knobs in `scripts/fetch_trends.py`:
- `momentum_score()` — the formula that ranks individual videos.
- `extract_topics()` — the phrase-clustering logic. The `len(vids) < 2` line is the threshold for what counts as a "trend" (a phrase must appear in at least 2 high-momentum videos).

### Restyle the site

Everything is in `styles.css`. The CSS variables at the top (`--bg`, `--accent`, `--f-display`, etc.) cover the whole palette and type system. Swap fonts in `index.html`'s Google Fonts link, swap colors in the `:root` block, done.

---

## Running locally

```bash
# 1. Fetch fresh data
export YOUTUBE_API_KEY="your_key_here"
pip install -r requirements.txt
python scripts/fetch_trends.py

# 2. Serve the site
python -m http.server 8000
# → http://localhost:8000
```

---

## Limitations to be aware of

- **The "most popular" chart isn't a perfect proxy for "emerging."** It's the strongest free signal YouTube exposes, but very young breakout videos sometimes haven't made it onto the chart yet. Topic clustering helps because a fresh video can ride the coattails of an established phrase.
- **Title-based topic detection misses video content.** A video about home espresso titled "I tried this for 30 days" gets clustered under "i tried" rather than "espresso." Treat the topic list as a starting point, not the final word.
- **No search-volume data.** The YouTube Data API doesn't expose search trends. For that, pair this with [Google Trends](https://trends.google.com/) (set source to YouTube Search). The two together give you a much fuller picture than either alone.
- **The API has a quota.** 10K units/day free. TubeRadar uses far less than that, but if you push the regions list to 20+ countries and crank the cron, you could hit it.

---

## License

MIT. Use it, fork it, sell a SaaS on top of it. Just don't pretend you wrote it from scratch.
