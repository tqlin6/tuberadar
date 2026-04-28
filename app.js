/* ---------------------------------------------------------------
   TubeRadar – frontend
   Loads data/trends.json and renders the feed.
   --------------------------------------------------------------- */

(async function () {
  const els = {
    themes:       document.getElementById('themes-list'),
    topics:       document.getElementById('topics-list'),
    videos:       document.getElementById('videos-list'),
    searches:     document.getElementById('searches-list'),
    updated:      document.getElementById('updated-at'),
    regionSelect: document.getElementById('region-select'),
    issue:        document.getElementById('issue-number'),
    themeToggle:  document.getElementById('theme-toggle'),
  };

  // ---------- Theme toggle ----------
  if (els.themeToggle) {
    els.themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try { localStorage.setItem('tuberadar:theme', next); } catch (_) {}
    });
  }

  let data;
  try {
    const res = await fetch('data/trends.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    showError(err.message);
    return;
  }

  // Track when the visitor last saw the feed, so we can highlight
  // themes that appeared since then. Read first, then update.
  const LAST_VISIT_KEY = 'tuberadar:last-visit';
  let lastVisitMs = 0;
  try {
    const stored = localStorage.getItem(LAST_VISIT_KEY);
    if (stored) lastVisitMs = parseInt(stored, 10) || 0;
  } catch (_) { /* localStorage unavailable, ignore */ }
  // Update it now so refreshing the page within seconds doesn't keep
  // re-marking everything as new.
  try {
    localStorage.setItem(LAST_VISIT_KEY, String(Date.now()));
  } catch (_) {}
  const isReturning = lastVisitMs > 0;
  const visitGapMs = Date.now() - lastVisitMs;
  // Only show "new since your last visit" if the gap is meaningful –
  // otherwise opening 5 tabs marks 5 different "visits" pointlessly.
  const showWhatsNew = isReturning && visitGapMs > 30 * 60 * 1000;

  // ---------- masthead ----------
  const updatedDate = new Date(data.generated_at);
  els.updated.textContent = formatRelative(updatedDate);
  els.updated.title = updatedDate.toLocaleString();
  els.issue.textContent = formatIssue(updatedDate);

  // ---------- Region selector ----------
  const REGION_KEY = 'tuberadar:region';
  let savedRegion = 'all';
  try { savedRegion = localStorage.getItem(REGION_KEY) || 'all'; } catch (_) {}

  // Populate the dropdown.
  const regionsMeta = data.regions_meta || (data.regions || []).map(r => ({ code: r, name: r }));
  if (els.regionSelect) {
    // Clear any existing options except the "ALL" option.
    els.regionSelect.innerHTML = '<option value="all">ALL</option>';
    for (const r of regionsMeta) {
      const opt = document.createElement('option');
      opt.value = r.code;
      opt.textContent = `${r.code} — ${r.name}`;
      els.regionSelect.appendChild(opt);
    }
    // Default-select the saved region if it exists in our list.
    const validRegions = ['all', ...regionsMeta.map(r => r.code)];
    if (!validRegions.includes(savedRegion)) savedRegion = 'all';
    els.regionSelect.value = savedRegion;

    els.regionSelect.addEventListener('change', () => {
      const newRegion = els.regionSelect.value;
      try { localStorage.setItem(REGION_KEY, newRegion); } catch (_) {}
      renderForRegion(newRegion);
    });
  }

  function regionMatches(item, region) {
    if (region === 'all') return true;
    if (item.region === region) return true;
    if (Array.isArray(item.regions) && item.regions.includes(region)) return true;
    return false;
  }

  function renderForRegion(region) {
    // ---------- emerging themes (always global - they're search-validated) ----------
    els.themes.removeAttribute('aria-busy');
    els.themes.innerHTML = '';

    if (!data.emerging_themes || data.emerging_themes.length === 0) {
      els.themes.innerHTML = '<li class="placeholder">No emerging themes detected in the current window. Check back later — themes need traction across multiple small creators before they show up here.</li>';
    } else {
      let newSinceLastVisit = 0;
      if (showWhatsNew) {
        newSinceLastVisit = data.emerging_themes.filter(t =>
          t.first_detected_at && new Date(t.first_detected_at).getTime() > lastVisitMs
        ).length;
      }
      if (newSinceLastVisit > 0) {
        const banner = document.createElement('li');
        banner.className = 'themes-banner';
        banner.innerHTML = `
          <span class="themes-banner__dot"></span>
          <span><strong>${newSinceLastVisit}</strong> new ${newSinceLastVisit === 1 ? 'theme has' : 'themes have'} surfaced since your last visit.</span>
        `;
        els.themes.appendChild(banner);
      }
      data.emerging_themes.forEach((theme, i) => {
        const isNew = showWhatsNew && theme.first_detected_at &&
          new Date(theme.first_detected_at).getTime() > lastVisitMs;
        els.themes.appendChild(renderTheme(theme, i + 1, isNew));
      });
    }

    // ---------- topics (filtered by region) ----------
    els.topics.removeAttribute('aria-busy');
    els.topics.innerHTML = '';

    const filteredTopics = (data.topics || []).filter(t => regionMatches(t, region));
    if (filteredTopics.length === 0) {
      const msg = region === 'all'
        ? 'No topics yet — the feed will populate after the next fetch.'
        : `No topics for this region right now. Try ALL or another region.`;
      els.topics.innerHTML = `<li class="placeholder">${msg}</li>`;
    } else {
      filteredTopics.forEach((topic, i) => {
        els.topics.appendChild(renderTopic(topic, i + 1));
      });
    }

    // ---------- videos (filtered by region) ----------
    els.videos.removeAttribute('aria-busy');
    els.videos.innerHTML = '';

    const filteredVideos = (data.breakout_videos || []).filter(v => regionMatches(v, region));
    if (filteredVideos.length === 0) {
      const msg = region === 'all'
        ? 'No videos yet.'
        : 'No videos for this region right now.';
      els.videos.innerHTML = `<li class="placeholder">${msg}</li>`;
    } else {
      filteredVideos.slice(0, 12).forEach((video, i) => {
        els.videos.appendChild(renderVideo(video, i + 1));
      });
    }

    // ---------- trending searches (always global) ----------
    if (els.searches) {
      els.searches.removeAttribute('aria-busy');
      els.searches.innerHTML = '';
      const searches = data.trending_searches || [];
      if (searches.length === 0) {
        els.searches.innerHTML = '<li class="placeholder">No search trends yet — populates after next fetch.</li>';
      } else {
        searches.forEach((s, i) => {
          els.searches.appendChild(renderSearchTerm(s, i + 1));
        });
      }
    }
  }

  // Initial render.
  renderForRegion(savedRegion);

  // ---------- helpers ----------

  function renderSearchTerm(term, rank) {
    const li = document.createElement('li');
    li.className = 'search-term';
    li.tabIndex = 0;

    const isNew = !!term.is_new;
    const newBadge = isNew ? '<span class="search-term__badge">NEW</span>' : '';

    li.innerHTML = `
      <div class="search-term__rank">${String(rank).padStart(2, '0')}</div>
      <div class="search-term__main">
        <div class="search-term__phrase">${escapeHtml(term.phrase)}</div>
        <span class="search-term__prefix">From "${escapeHtml(term.prefix)}…"</span>
      </div>
      ${newBadge}
    `;

    // Clicking opens a YouTube search for the term in a new tab.
    const ytUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(term.phrase)}`;
    li.addEventListener('click', () => window.open(ytUrl, '_blank', 'noopener'));
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        window.open(ytUrl, '_blank', 'noopener');
      }
    });

    return li;
  }

  function renderTheme(theme, rank, isNew) {
    const li = document.createElement('li');
    li.className = 'theme' + (isNew ? ' theme--new' : '');
    li.tabIndex = 0;

    const examples = (theme.example_videos || []).map(v => `
      <a class="example" href="${escapeAttr(v.url)}" target="_blank" rel="noopener">
        <div class="example__thumb" style="background-image:url('${escapeAttr(v.thumbnail)}')"></div>
        <div class="example__body">
          <div class="example__title">${escapeHtml(v.title)}</div>
          <div class="example__meta">${escapeHtml(v.channel)} · ${formatSubs(v.subscribers)} subs · ${formatRelativeFromIso(v.published_at)}</div>
        </div>
      </a>
    `).join('');

    const newBadge = isNew ? '<span class="theme__new-badge">NEW</span>' : '';
    const firstDetected = theme.first_detected_at
      ? `<span class="theme__detected">First detected ${formatRelativeFromIso(theme.first_detected_at)}</span>`
      : '';

    li.innerHTML = `
      <div class="theme__rank">${String(rank).padStart(2, '0')}</div>
      <div class="theme__main">
        <div class="theme__phrase">${escapeHtml(theme.phrase)}${newBadge}</div>
        <div class="theme__stats">
          <span class="theme__stat">
            <strong>${theme.channel_count}</strong>
            <span class="theme__stat-label">creators</span>
          </span>
          <span class="theme__stat">
            <strong>${theme.video_count}</strong>
            <span class="theme__stat-label">uploads / ${theme.window_hours}h</span>
          </span>
          <span class="theme__stat">
            <strong>${theme.uploads_per_hour}</strong>
            <span class="theme__stat-label">creators / hr</span>
          </span>
        </div>
        ${firstDetected}
        <div class="theme__examples">${examples}</div>
      </div>
    `;

    li.addEventListener('click', (e) => {
      if (e.target.closest('.example')) return;
      li.classList.toggle('is-open');
    });
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        li.classList.toggle('is-open');
      }
    });

    return li;
  }

  function renderTopic(topic, rank) {
    const li = document.createElement('li');
    li.className = 'topic';
    li.tabIndex = 0;

    const examples = (topic.example_videos || []).map(v => `
      <a class="example" href="${escapeAttr(v.url)}" target="_blank" rel="noopener">
        <div class="example__thumb" style="background-image:url('${escapeAttr(v.thumbnail)}')"></div>
        <div class="example__body">
          <div class="example__title">${escapeHtml(v.title)}</div>
          <div class="example__meta">${escapeHtml(v.channel)} · ${formatViews(v.views)} views · ${formatAge(v.age_hours)}</div>
        </div>
      </a>
    `).join('');

    li.innerHTML = `
      <div class="topic__rank">${String(rank).padStart(2, '0')}</div>
      <div class="topic__main">
        <div class="topic__phrase">${escapeHtml(topic.phrase)}</div>
        <div class="topic__meta">
          <span>${topic.video_count} videos carrying it</span>
          <span>${formatTotalViews(topic.example_videos)} combined views</span>
        </div>
        <div class="topic__examples">${examples}</div>
      </div>
      <div class="topic__score">
        <strong>${topic.momentum.toFixed(1)}</strong>
        <span class="topic__score-label">momentum</span>
      </div>
    `;

    li.addEventListener('click', (e) => {
      // Don't toggle if user clicked an example link
      if (e.target.closest('.example')) return;
      li.classList.toggle('is-open');
    });
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        li.classList.toggle('is-open');
      }
    });

    return li;
  }

  function renderVideo(video, rank) {
    const li = document.createElement('li');
    li.className = 'video';

    li.innerHTML = `
      <div class="video__thumb" style="background-image:url('${escapeAttr(video.thumbnail)}')">
        <span class="video__rank">${String(rank).padStart(2, '0')}</span>
      </div>
      <div class="video__body">
        <div class="video__title">${escapeHtml(video.title)}</div>
        <div class="video__channel">${escapeHtml(video.channel)}</div>
        <div class="video__meta">
          <span class="vph">${formatViews(video.views_per_hour)}/hr</span>
          <span>${formatViews(video.views)} views</span>
          <span>${formatAge(video.age_hours)}</span>
          <span>${escapeHtml(video.category || '')}</span>
        </div>
      </div>
    `;

    li.addEventListener('click', () => {
      window.open(video.url, '_blank', 'noopener');
    });

    return li;
  }

  function showError(msg) {
    if (els.themes) {
      els.themes.removeAttribute('aria-busy');
      els.themes.innerHTML = '';
    }
    if (els.topics) {
      els.topics.removeAttribute('aria-busy');
      els.topics.innerHTML = `<li class="placeholder">Couldn't load the feed (${escapeHtml(msg)}). If you've just deployed, the first GitHub Action run may still be in progress.</li>`;
    }
    if (els.videos) {
      els.videos.removeAttribute('aria-busy');
      els.videos.innerHTML = '';
    }
    if (els.searches) {
      els.searches.removeAttribute('aria-busy');
      els.searches.innerHTML = '';
    }
  }

  function formatViews(n) {
    if (n == null) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
  }

  function formatAge(hours) {
    if (hours == null) return '';
    if (hours < 1)   return 'just now';
    if (hours < 24)  return `${Math.round(hours)}h ago`;
    const days = hours / 24;
    if (days < 7)    return `${Math.round(days)}d ago`;
    return `${Math.round(days / 7)}w ago`;
  }

  function formatRelative(date) {
    const diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60)        return 'just now';
    if (diff < 3600)      return `${Math.round(diff/60)}m ago`;
    if (diff < 86400)     return `${Math.round(diff/3600)}h ago`;
    return `${Math.round(diff/86400)}d ago`;
  }

  function formatRelativeFromIso(iso) {
    if (!iso) return '';
    return formatRelative(new Date(iso));
  }

  function formatSubs(n) {
    if (n == null) return '—';
    if (n === 0)       return 'hidden';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(n);
  }

  function formatIssue(date) {
    // YYYY-DDD style issue number for the cron-published feel.
    const y = date.getUTCFullYear();
    const start = Date.UTC(y, 0, 0);
    const day = Math.floor((date.getTime() - start) / 86400000);
    return `${y}.${String(day).padStart(3, '0')}`;
  }

  function formatTotalViews(videos) {
    const total = (videos || []).reduce((s, v) => s + (v.views || 0), 0);
    return formatViews(total);
  }

  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }
  function escapeAttr(s) { return escapeHtml(s); }
})();
