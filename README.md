TubeRadar
> A signal feed of emerging YouTube topics for content creators. Refreshed throughout the day.
TubeRadar surfaces emerging trends on YouTube two ways:
Emerging themes — topics that many different small/mid creators (under 1M subscribers) have started uploading about in the last 12 hours. This is the strongest signal of a topic catching fire across YouTube right now, because it filters out the case where one big channel posts and dominates the conversation.
Topics gaining momentum — phrases recurring across the highest-velocity videos currently on YouTube's "most popular" charts. Useful for spotting hooks and formats that are working.
The site is a static HTML/CSS/JS page; the data is refreshed by a Python script that runs on GitHub Actions and writes a JSON file back into the repo.
Total cost to run: $0/month.
---
How it works
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
The Python script calls the YouTube Data API v3 (`videos.list?chart=mostPopular`) for several content-creator-relevant categories across the regions you configure.
For every video it computes a momentum score — a log-smoothed view-velocity (views/hour since publish), weighted by engagement.
It tokenizes every title, extracts 1–3 word phrases, drops stopwords, and identifies phrases that appear across multiple high-momentum videos. Those are your trending topics.
The result is dumped to `data/trends.json` and committed back to the repo.
GitHub Pages serves the static site. The frontend `fetch()`es the JSON and renders it.
---
Deploy in ~10 minutes
1. Get a YouTube Data API key (free)
Go to https://console.cloud.google.com/.
Create a new project (any name).
Open APIs & Services → Library, search "YouTube Data API v3", click Enable.
Open APIs & Services → Credentials, click Create credentials → API key.
Copy the key. Keep it somewhere safe.
The free tier is 10,000 quota units/day. With the default every-6-hours schedule and 6 theme candidates per run, TubeRadar uses about 2,500 units/day — comfortably within the free tier. The script also detects quota-exceeded errors and stops calling the API immediately rather than spamming failed requests. If a fetch fails entirely, the previous good data stays on the site (the script never overwrites with empty results).
2. Push this code to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/tuberadar.git
git push -u origin main
```
3. Add the API key as a repo secret
In your GitHub repo, go to Settings → Secrets and variables → Actions.
Click New repository secret.
Name: `YOUTUBE_API_KEY`. Value: the key from step 1. Save.
(Optional) On the same page, click the Variables tab and add `TUBERADAR_REGIONS` with a comma-separated list like `US,GB,CA,AU` to broaden coverage. Default is `US,GB`.
4. Turn on GitHub Pages
Settings → Pages.
Under Source, select Deploy from a branch.
Branch: `main`, folder: `/ (root)`. Save.
Wait ~30 seconds. Your site will be live at `https://YOUR-USERNAME.github.io/tuberadar/`.
5. Trigger the first fetch
The cron only runs at scheduled times, but you can kick it off manually:
Go to the Actions tab.
Click Update trends in the sidebar.
Click Run workflow → Run workflow.
After ~30 seconds the action should complete and commit a fresh `data/trends.json`. Reload your site — it'll show real data.
---
Customizing
Change which categories get fetched
Edit the `CATEGORIES` dict at the top of `scripts/fetch_trends.py`. The keys are YouTube's video category IDs.
Change which countries get fetched
Set the `TUBERADAR_REGIONS` repository variable to a comma-separated list of ISO 3166-1 alpha-2 codes (e.g. `US,GB,CA,AU,DE,IN`).
Change the update frequency
Edit the `cron:` line in `.github/workflows/update-trends.yml`. Default is `0 */3 * * *` (every 3 hours). If you want to fetch more often, reduce `THEME_CANDIDATES` in the Python script proportionally to stay within the YouTube API's 10,000 units/day free quota. Public GitHub repos have unlimited Actions minutes; private repos are limited to 2,000/month, which is still ~10x what TubeRadar needs.
Change how trending is defined
Two knobs in `scripts/fetch_trends.py`:
`momentum_score()` — the formula that ranks individual videos.
`extract_topics()` — the phrase-clustering logic. The `len(vids) < 2` line is the threshold for what counts as a "trend" (a phrase must appear in at least 2 high-momentum videos).
Restyle the site
Everything is in `styles.css`. The CSS variables at the top (`--bg`, `--accent`, `--f-display`, etc.) cover the whole palette and type system. Swap fonts in `index.html`'s Google Fonts link, swap colors in the `:root` block, done.
---
Running locally
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
Limitations to be aware of
Phrase-based clustering misses brand-new trends. If a topic is so new that no two creators have settled on a shared phrase yet, neither feed will catch it. For 95% of useful trends, phrase clustering works great — but it's worth knowing the edge.
Title-based detection misses video content. A video about home espresso titled "I tried this for 30 days" gets clustered under "i tried" rather than "espresso." The "Emerging themes" feed is more resilient to this than "Topics" because it validates against fresh search results, but neither is perfect.
No search-volume data. The YouTube Data API doesn't expose search trends. For that, pair this with Google Trends (set source to YouTube Search). The two together give you a much fuller picture than either alone.
The API has a quota. 10K units/day free. TubeRadar uses ~1,000/day with default settings. If you push the regions list to 20+ countries or crank the cron, you could hit it.
---
License
MIT. Use it, fork it, sell a SaaS on top of it. Just don't pretend you wrote it from scratch.
