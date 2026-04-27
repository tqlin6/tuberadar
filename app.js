/* ---------------------------------------------------------------
   TubeRadar – frontend
   Loads data/trends.json and renders the feed.
   --------------------------------------------------------------- */

(async function () {
  const els = {
    topics:    document.getElementById('topics-list'),
    videos:    document.getElementById('videos-list'),
    updated:   document.getElementById('updated-at'),
    regions:   document.getElementById('regions'),
    issue:     document.getElementById('issue-number'),
  };

  let data;
  try {
    const res = await fetch('data/trends.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    showError(err.message);
    return;
  }

  // ---------- masthead ----------
  const updatedDate = new Date(data.generated_at);
  els.updated.textContent = formatRelative(updatedDate);
  els.updated.title = updatedDate.toLocaleString();
  els.regions.textContent = (data.regions || []).join(' · ');
  els.issue.textContent = formatIssue(updatedDate);

  // ---------- topics ----------
  els.topics.removeAttribute('aria-busy');
  els.topics.innerHTML = '';

  if (!data.topics || data.topics.length === 0) {
    els.topics.innerHTML = '<li class="placeholder">No topics yet — the feed will populate after the next fetch.</li>';
  } else {
    data.topics.forEach((topic, i) => {
      els.topics.appendChild(renderTopic(topic, i + 1));
    });
  }

  // ---------- videos ----------
  els.videos.removeAttribute('aria-busy');
  els.videos.innerHTML = '';

  if (!data.breakout_videos || data.breakout_videos.length === 0) {
    els.videos.innerHTML = '<li class="placeholder">No videos yet.</li>';
  } else {
    data.breakout_videos.slice(0, 12).forEach((video, i) => {
      els.videos.appendChild(renderVideo(video, i + 1));
    });
  }

  // ---------- helpers ----------

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
    els.topics.removeAttribute('aria-busy');
    els.topics.innerHTML = `<li class="placeholder">Couldn't load the feed (${escapeHtml(msg)}). If you've just deployed, the first GitHub Action run may still be in progress.</li>`;
    els.videos.removeAttribute('aria-busy');
    els.videos.innerHTML = '';
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
