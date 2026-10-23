// ==========================================================================
//  EMPLOYMENT RESULT — SUPERCHARGED HIGH-SPEED ENGINE (v2.5)
//  5-Box Portal Architecture with Equal-Height Grid & Instant WhatsApp Share
// ==========================================================================

var globalAllPosts = [];
var rawFeedEntries = [];

// 1. High-Performance Client-Side Caching (0ms Instant Load)
function getCache(key) {
  try {
    var raw = sessionStorage.getItem(key);
    if (!raw) return null;
    var parsed = JSON.parse(raw);
    if (Date.now() - parsed.ts < 300000) { // 5-minute validity
      return parsed.val;
    }
  } catch(e) {}
  return null;
}

function setCache(key, val) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ ts: Date.now(), val: val }));
  } catch(e) {}
}

// 2. Animated Skeleton Preloaders
function injectSkeletons() {
  var lists = ['list-result', 'list-admit', 'list-job', 'list-key', 'list-syl'];
  var skelHtml = '';
  for (var i = 0; i < 6; i++) {
    skelHtml += '<li style="padding:10px 4px; display:flex; align-items:center; gap:8px;">' +
                '<span style="display:inline-block; width:45px; height:20px; background:#e2e8f0; border-radius:4px; animation:srPulse 1.2s infinite ease-in-out;"></span>' +
                '<span style="display:inline-block; width:' + (60 + (i % 4) * 10) + '%; height:16px; background:#f1f5f9; border-radius:4px; animation:srPulse 1.2s infinite ease-in-out;"></span>' +
                '</li>';
  }
  lists.forEach(function(id) {
    var el = document.getElementById(id);
    if (el && el.children.length === 0) {
      el.innerHTML = skelHtml;
    }
  });
}

// Helper: Normalize Path for exact URL comparison
function normalizePath(u) {
  if (!u) return '';
  try {
    var parsed = new URL(u, window.location.origin);
    return parsed.pathname.toLowerCase().replace(/\/+$/, '');
  } catch(e) {
    return u.toLowerCase().split('?')[0].replace(/\/+$/, '');
  }
}

// Resizer Tool Page Visibility
(function checkResizerPage() {
  if (window.location.pathname.indexOf('/p/photo-signature-resizer') !== -1) {
    var rBox = document.getElementById('resizer-tool-wrapper');
    if (rBox) rBox.style.display = 'block';
  }
})();

// 3. Theme Controller (Dark Mode)
function applySavedTheme() {
  try {
    var saved = localStorage.getItem('sr_dark_mode');
    var body = document.body;
    var icon = document.getElementById('theme-icon');
    if (saved === 'enabled') {
      body.classList.add('dark-mode');
      if (icon) icon.innerText = '☀️';
    } else {
      body.classList.remove('dark-mode');
      if (icon) icon.innerText = '🌙';
    }
  } catch(e) {}
}

function toggleTheme() {
  var body = document.body;
  var isDark = body.classList.contains('dark-mode');
  localStorage.setItem('sr_dark_mode', isDark ? 'disabled' : 'enabled');
  applySavedTheme();
}
applySavedTheme();

// 4. Age Calculator Anchor Scroll Handler
function handleAgeCalculator(e) {
  if (window.location.pathname === '/' || window.location.pathname === '') {
    var el = document.getElementById('ageCalculator');
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }
}

// 5. Smart Badge & Department Detection
function getSmartBadges(title) {
  var t = title.toUpperCase();
  var org = '';
  var urgency = '';

  if (t.indexOf('SSC') > -1) org = '<span class="org-badge badge-ssc">SSC</span>';
  else if (t.indexOf('RAILWAY') > -1 || t.indexOf('RRB') > -1) org = '<span class="org-badge badge-rrb">RRB</span>';
  else if (t.indexOf('POLICE') > -1 || t.indexOf('CONSTABLE') > -1 || t.indexOf('BSF') > -1 || t.indexOf('AIRFORCE') > -1) org = '<span class="org-badge badge-police">DEFENCE</span>';
  else if (t.indexOf('BANK') > -1 || t.indexOf('IBPS') > -1 || t.indexOf('SBI') > -1) org = '<span class="org-badge badge-bank">BANK</span>';
  else if (t.indexOf('UPSC') > -1 || t.indexOf('BPSC') > -1 || t.indexOf('MPPSC') > -1 || t.indexOf('HPSC') > -1 || t.indexOf('RPSC') > -1 || t.indexOf('UPSSSC') > -1) org = '<span class="org-badge badge-upsc">PSC</span>';
  else org = '<span class="org-badge badge-default">GOVT</span>';

  if (t.indexOf('LAST DATE') > -1 || t.indexOf('ENDING') > -1 || t.indexOf('OUT') > -1) {
    urgency = '<span class="urgency-badge urgency-ending">⏳ Live</span>';
  }
  return { org: org, urgency: urgency };
}

// Quick WhatsApp Share Helper
function shareToWhatsApp(title, link) {
  var fullUrl = link.indexOf('http') === 0 ? link : (window.location.origin + link);
  var text = '🔥 Check this update: ' + title + '\n\n🔗 Link: ' + fullUrl;
  window.open('https://api.whatsapp.com/send?text=' + encodeURIComponent(text), '_blank');
}

// 6. Interactive Quick Filter Chips Handler
window.filterFeed = function(tag, btnEl) {
  document.querySelectorAll('.chip-btn').forEach(function(b) { b.classList.remove('active'); });
  if (btnEl) btnEl.classList.add('active');
  renderHomepageBoxes(tag);
};

// Live Category Counts Updater
function updateCategoryLiveCounts(posts) {
  var counts = { Result: 0, 'Admit Card': 0, Job: 0, 'Answer Key': 0, Syllabus: 0 };
  (posts || []).forEach(function(p) {
    if (counts[p.cat] !== undefined) counts[p.cat]++;
    else counts.Job++;
  });
  var bRes = document.getElementById('badge-count-res');
  var bAdm = document.getElementById('badge-count-adm');
  var bJob = document.getElementById('badge-count-job');
  var bKey = document.getElementById('badge-count-key');
  var bSyl = document.getElementById('badge-count-syl');
  if (bRes) bRes.innerText = counts.Result + ' Live';
  if (bAdm) bAdm.innerText = counts['Admit Card'] + ' Live';
  if (bJob) bJob.innerText = counts.Job + ' Live';
  if (bKey) bKey.innerText = counts['Answer Key'] + ' Live';
  if (bSyl) bSyl.innerText = counts.Syllabus + ' Live';
}

function renderHomepageBoxes(filterTag) {
  var resList = document.getElementById('list-result');
  var admList = document.getElementById('list-admit');
  var jobList = document.getElementById('list-job');
  var keyList = document.getElementById('list-key');
  var sylList = document.getElementById('list-syl');

  if (!resList || !admList || !jobList) return;

  var resHtml = '', admHtml = '', jobHtml = '', keyHtml = '', sylHtml = '';
  var cRes = 0, cAdm = 0, cJob = 0, cKey = 0, cSyl = 0;

  rawFeedEntries.forEach(function(p) {
    var tl = p.title.toUpperCase();

    if (filterTag && filterTag !== 'ALL') {
      if (filterTag === 'SSC' && tl.indexOf('SSC') === -1) return;
      if (filterTag === 'RAILWAY' && tl.indexOf('RAILWAY') === -1 && tl.indexOf('RRB') === -1) return;
      if (filterTag === 'POLICE' && tl.indexOf('POLICE') === -1 && tl.indexOf('CONSTABLE') === -1 && tl.indexOf('BSF') === -1 && tl.indexOf('AIRFORCE') === -1) return;
      if (filterTag === 'BANK' && tl.indexOf('BANK') === -1 && tl.indexOf('IBPS') === -1 && tl.indexOf('SBI') === -1) return;
      if (filterTag === '10TH' && tl.indexOf('10TH') === -1 && tl.indexOf('12TH') === -1 && tl.indexOf('INTER') === -1 && tl.indexOf('MATRIC') === -1) return;
    }

    var badges = getSmartBadges(p.title);
    var safeTitle = p.title.replace(/'/g, "\\'");
    var item = '<li>' + badges.org + 
               '<a href="' + p.link + '">' + p.title + '</a>' + 
               badges.urgency +
               '<button class="btn-item-share" onclick="shareToWhatsApp(\'' + safeTitle + '\', \'' + p.link + '\')" title="Share to WhatsApp">💬</button>' +
               '</li>';

    if (p.cat === 'Answer Key') {
      if (cKey < 15) { keyHtml += item; cKey++; }
    } else if (p.cat === 'Syllabus') {
      if (cSyl < 15) { sylHtml += item; cSyl++; }
    } else if (p.cat === 'Result') {
      if (cRes < 20) { resHtml += item; cRes++; }
    } else if (p.cat === 'Admit Card') {
      if (cAdm < 20) { admHtml += item; cAdm++; }
    } else {
      if (cJob < 20) { jobHtml += item; cJob++; }
    }
  });

  resList.innerHTML = resHtml || '<li style="color:#64748b;">No updates found.</li>';
  admList.innerHTML = admHtml || '<li style="color:#64748b;">No updates found.</li>';
  jobList.innerHTML = jobHtml || '<li style="color:#64748b;">No updates found.</li>';
  if (keyList) keyList.innerHTML = keyHtml || '<li style="color:#64748b;">No updates found.</li>';
  if (sylList) sylList.innerHTML = sylHtml || '<li style="color:#64748b;">No updates found.</li>';
}

// 7. Live Search Engine
function setupLiveSearch() {
  var input = document.getElementById('site-search-input');
  var list = document.getElementById('search-results-list');
  if (!input || !list) return;

  input.addEventListener('input', function() {
    var query = this.value.trim().toLowerCase();
    if (query.length < 2) {
      list.style.display = 'none';
      list.innerHTML = '';
      return;
    }

    var matched = [];
    for (var i = 0; i < globalAllPosts.length; i++) {
      var p = globalAllPosts[i];
      if (p.title.toLowerCase().indexOf(query) > -1) {
        matched.push(p);
        if (matched.length >= 8) break;
      }
    }

    if (matched.length > 0) {
      var html = '';
      for (var j = 0; j < matched.length; j++) {
        var badges = getSmartBadges(matched[j].title);
        html += '<li onclick="window.location.href=\'' + matched[j].link + '\'">' +
                  badges.org +
                  '<span style="flex:1;">' + matched[j].title + '</span>' +
                '</li>';
      }
      list.innerHTML = html;
      list.style.display = 'block';
    } else {
      list.innerHTML = '<li style="color:#64748b;text-align:center;">No matching vacancy found</li>';
      list.style.display = 'block';
    }
  });

  document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-box-wrapper')) {
      list.style.display = 'none';
    }
  });
}

// Export initialization for modular use
if (typeof window !== 'undefined') {
  window.initPortal = function() {
    applySavedTheme();
    setupLiveSearch();
  };
}
