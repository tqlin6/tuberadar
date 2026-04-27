# AdSense setup guide

This guide walks you through monetising TubeRadar with Google AdSense. Follow it **after** your site is live (i.e. after you've completed the steps in `README.md`).

## Why you need to wait

Google won't approve a brand-new site with no content or visitors. Realistic timeline:

1. **Week 0:** Deploy TubeRadar. Wait for the first GitHub Action to run so you have real data on the site.
2. **Weeks 1–2:** Get a small amount of organic traffic (share on Twitter/Reddit/forums where content creators hang out — r/NewTubers, r/PartneredYoutube, r/youtubers, etc.).
3. **Week 2 onward:** Apply to AdSense.

Sites are sometimes rejected for "low value content" — having some traffic and a clearly useful site beats applying on day one.

## Step 1: Apply to AdSense

1. Go to <https://www.google.com/adsense> and sign in with the Google account you want to receive payments to.
2. Click **Get started**.
3. Enter your site URL (e.g. `https://yourname.github.io/tuberadar/`).
4. Pick your country, accept terms.
5. Provide your name, address, and phone number — these must match your bank details for payouts.
6. Google gives you a code snippet. **The code is already in TubeRadar's `index.html`** — you just need to swap in your real Publisher ID. See Step 2.
7. Submit your site for review. **Approval takes anywhere from a few days to a few weeks.** You'll get an email.

## Step 2: Plug in your Publisher ID

Once you're in AdSense (even before approval), you'll have a **Publisher ID** that looks like `ca-pub-1234567890123456`. You need to put it in three places.

### A. In `index.html`

Open `index.html`. Use Find & Replace (Ctrl+F or Cmd+F → there's usually a "replace" option):

- **Find:** `ca-pub-XXXXXXXXXXXXXXXX`
- **Replace with:** your real ID, e.g. `ca-pub-1234567890123456`
- **Replace All** — there should be 5 occurrences (1 in the comment, 1 in the script tag, 3 in the ad slots).

### B. In `privacy.html`

Open `privacy.html`. Find the placeholder `your-email@example.com` near the bottom and replace it with a real contact email.

### C. In `ads.txt`

Open `ads.txt` (it's just one line). Replace `pub-XXXXXXXXXXXXXXXX` with your real ID — but **only the part after `ca-`**. So if your full ID is `ca-pub-1234567890123456`, the file should read:

```
google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0
```

### How to commit your changes back to GitHub

1. On GitHub, go to your `tuberadar` repo.
2. Click on the file you want to edit (e.g. `index.html`).
3. Click the pencil icon (top right of the file content) to edit in the browser.
4. Make your changes.
5. Scroll to the bottom, type a short message like "Update AdSense ID", click **Commit changes**.
6. Repeat for `privacy.html` and `ads.txt`.

GitHub Pages will redeploy automatically within a minute.

## Step 3: Create the actual ad units

Until you do this, the ad slots will be empty rectangles.

1. In the AdSense dashboard, go to **Ads → By ad unit → Create new ad unit**.
2. Choose **Display ads**.
3. Name it something memorable like "TubeRadar top banner".
4. Pick **Responsive** size.
5. Click **Create**. Google gives you a code snippet that includes a `data-ad-slot` ID — a long number.
6. Copy that slot ID.

Now back in `index.html`, replace the placeholder `data-ad-slot` values:

- The first ad slot has `data-ad-slot="0000000001"` — replace with your first ad unit's slot ID.
- The second has `data-ad-slot="0000000002"` — create a second ad unit, paste that ID.
- The third has `data-ad-slot="0000000003"` — create a third ad unit, paste that ID.

You can use the same ad unit ID for all three slots if you want (Google permits it), but creating three separate units gives you better analytics on which placement earns the most.

## Step 4: Wait for approval

After applying, Google reviews your site. They check:

- The site loads and works
- It has actual content (TubeRadar passes — it's a working tool)
- It has a privacy policy (✓ — `privacy.html`)
- It complies with their content policies (no adult, hateful, or illegal content — TubeRadar is fine)
- It's not pure copies of other sites' content (TubeRadar is original analysis — fine)

If approved, ads start showing automatically. If rejected, the email tells you why — fix it and reapply.

## What you'll earn (realistic expectations)

For a niche tool site like TubeRadar:

| Monthly visitors | Estimated monthly earnings |
| ---------------- | -------------------------- |
| 1,000            | $1 – $5                    |
| 10,000           | $10 – $50                  |
| 100,000          | $100 – $500                |
| 1,000,000        | $1,000 – $5,000            |

Variance is huge — depends on country mix (US/UK traffic earns 5–10× what some other regions do), niche, and ad placement. Content creator audiences tend to be on the higher end since they're commercially valuable to advertisers.

**Payouts:** Google holds your earnings until you hit $100, then pays via bank transfer once a month.

## Common rejection reasons (and fixes)

| Reason                              | Fix                                                                                       |
| ----------------------------------- | ----------------------------------------------------------------------------------------- |
| "Low value content"                 | Wait longer, get more traffic, maybe write a short blog post or two on the site.          |
| "Site not ready"                    | Make sure your data is loading and the site looks complete.                               |
| "Subdomain not eligible"            | Buy a custom domain (~$10/year) and point it at your GitHub Pages site.                   |
| "Privacy policy missing"            | You have one (`privacy.html`) — make sure you actually filled in your contact email.      |
| "Not enough unique content"         | Add an "About" page, a methodology page, or a small blog explaining how trends are spotted. |

## Optional: getting a custom domain

A custom domain (`tuberadar.com`) significantly improves your AdSense approval chances and looks more professional.

1. Buy a domain at <https://www.namecheap.com> or <https://www.cloudflare.com/products/registrar/> (Cloudflare sells at cost, often the cheapest).
2. In your GitHub repo's **Settings → Pages**, enter your custom domain.
3. In your domain registrar's DNS settings, add the records GitHub tells you to add (it's a copy-paste job — full instructions at <https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site>).
4. Wait a few minutes for DNS to update. Tick "Enforce HTTPS" in GitHub Pages settings once it appears.

That's it.
