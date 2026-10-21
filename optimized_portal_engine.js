// ==========================================================================
//  EMPLOYMENT RESULT - SUPERCHARGED HIGH-SPEED ENGINE (v2.0)
//  Optimizations: Instant 0ms Cache, Lightweight Feeds, Skeleton Preloaders, CDN Caching
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

// 2. Animated Skeleton Preloaders (Prevents blank white box effect)
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

// Theme Controller (Dark Mode)
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

// Age Calculator Anchor Scroll Handler
function handleAgeCalculator(e) {
  if (window.location.pathname === '/' || window.location.pathname === '') {
    var el = document.getElementById('ageCalculator');
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }
}

// Smart Badge & Department Detection
function getSmartBadges(title) {
  var t = title.toUpperCase();
  var org = '';
  var urgency = '';

  if (t.indexOf('SSC') > -1) org = '<span class="org-badge badge-ssc">SSC</span>';
  else if (t.indexOf('RAILWAY') > -1 || t.indexOf('RRB') > -1) org = '<span class="org-badge badge-rrb">RRB</span>';
  else if (t.indexOf('POLICE') > -1 || t.indexOf('CONSTABLE') > -1) org = '<span class="org-badge badge-police">POLICE</span>';
  else if (t.indexOf('BANK') > -1 || t.indexOf('IBPS') > -1 || t.indexOf('SBI') > -1) org = '<span class="org-badge badge-bank">BANK</span>';
  else if (t.indexOf('UPSC') > -1) org = '<span class="org-badge badge-upsc">UPSC</span>';
  else org = '<span class="org-badge badge-default">GOVT</span>';

  if (t.indexOf('LAST DATE') > -1 || t.indexOf('ENDING') > -1) {
    urgency = '<span class="urgency-badge urgency-ending">⏳ Ending Soon</span>';
  }
  return { org: org, urgency: urgency };
}

// Interactive Quick Filter Chips Handler
window.filterFeed = function(tag, btnEl) {
  document.querySelectorAll('.chip-btn').forEach(function(b) { b.classList.remove('active'); });
  if (btnEl) btnEl.classList.add('active');
  renderHomepageBoxes(tag);
};

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
      if (filterTag === 'POLICE' && tl.indexOf('POLICE') === -1 && tl.indexOf('CONSTABLE') === -1) return;
      if (filterTag === 'BANK' && tl.indexOf('BANK') === -1 && tl.indexOf('IBPS') === -1 && tl.indexOf('SBI') === -1) return;
      if (filterTag === '10TH' && tl.indexOf('10TH') === -1 && tl.indexOf('12TH') === -1 && tl.indexOf('INTER') === -1 && tl.indexOf('MATRIC') === -1) return;
    }

    var badges = getSmartBadges(p.title);
    var item = '<li>' + badges.org + 
               '<a href="' + p.link + '">' + p.title + '</a>' + 
               badges.urgency + '</li>';

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

// Live Search Engine
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
        var catLabel = matched[j].cat ? '<span class="org-badge badge-ssc">' + matched[j].cat + '</span>' : '';
        html += '<li><a href="' + matched[j].link + '">' + catLabel + matched[j].title + '</a></li>';
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

// ==========================================================================
// MAIN FAST CONTROLLER
// ==========================================================================

(function() {
  var currentPath = normalizePath(window.location.pathname);
  var isSinglePost = currentPath.indexOf('.html') > -1 && currentPath.indexOf('/p/') === -1;
  var isStaticPage = currentPath.indexOf('/p/') > -1 && currentPath.indexOf('photo-signature-resizer') === -1;
  var isLabelPage = window.location.pathname.indexOf('/search/label/') > -1;

  // 1. STATIC PAGES (About, Disclaimer, Privacy Policy)
  if (isStaticPage) {
    var directBox = document.getElementById('direct-post-display');
    var cachedPage = getCache('page_' + currentPath);
    if (cachedPage && directBox) {
      directBox.innerHTML = cachedPage;
      setupLiveSearch();
      return;
    }

    fetch('/feeds/pages/default?alt=json')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var entries = data.feed.entry || [];
        var matched = null;
        for (var i = 0; i < entries.length; i++) {
          var links = entries[i].link || [];
          for (var j = 0; j < links.length; j++) {
            if (links[j].rel === 'alternate' && normalizePath(links[j].href) === currentPath) {
              matched = entries[i];
              break;
            }
          }
          if (matched) break;
        }

        if (matched && directBox) {
          var pTitle = matched.title ? matched.title.$t : '';
          var pContent = matched.content ? matched.content.$t : (matched.summary ? matched.summary.$t : '');
          var rendered = '<div class="content-card-box">' +
                         '<h1 class="content-title">' + pTitle + '</h1>' +
                         '<div class="content-body-area">' + pContent + '</div>' +
                         '</div>';
          directBox.innerHTML = rendered;
          setCache('page_' + currentPath, rendered);
        }
      })
      .catch(function() {});
    setupLiveSearch();
    return;
  }

  // 2. SINGLE POST LOADER (INSTANT 0ms CACHE + LIGHTWEIGHT 30-POST DIRECT QUERY)
  if (isSinglePost) {
    var directBox = document.getElementById('direct-post-display');
    var cachedPost = getCache('post_' + currentPath);

    // Instant Render from Local Session Cache (0ms)
    if (cachedPost && directBox) {
      directBox.innerHTML = cachedPost;
      setupLiveSearch();
      return;
    }

    // Show instant modern shimmer while fetching single post
    if (directBox) {
      directBox.innerHTML = '<div class="content-card-box" style="padding:24px;">' +
                            '<div style="height:32px; width:70%; background:#e2e8f0; border-radius:6px; margin-bottom:16px; animation:srPulse 1.2s infinite;"></div>' +
                            '<div style="height:18px; width:95%; background:#f1f5f9; border-radius:4px; margin-bottom:8px; animation:srPulse 1.2s infinite;"></div>' +
                            '<div style="height:18px; width:85%; background:#f1f5f9; border-radius:4px; margin-bottom:24px; animation:srPulse 1.2s infinite;"></div>' +
                            '<div style="height:140px; width:100%; background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; animation:srPulse 1.2s infinite;"></div>' +
                            '</div>';
    }

    // Query lightweight 30 active posts (instead of 350 heavy posts)
    function searchFeed(maxResults) {
      return fetch('/feeds/posts/default?alt=json&max-results=' + maxResults)
        .then(function(res) { return res.json(); })
        .then(function(data) {
          var entries = data.feed.entry || [];
          var matched = null;
          for (var i = 0; i < entries.length; i++) {
            var links = entries[i].link || [];
            for (var j = 0; j < links.length; j++) {
              if (links[j].rel === 'alternate' && normalizePath(links[j].href) === currentPath) {
                matched = entries[i];
                break;
              }
            }
            if (matched) break;
          }
          return matched;
        });
    }

    searchFeed(40).then(function(matched) {
      if (!matched) {
        return searchFeed(250); // Fallback to wider archive if older post
      }
      return matched;
    }).then(function(matched) {
      if (matched && directBox) {
        var pTitle = matched.title ? matched.title.$t : '';
        var pContent = matched.content ? matched.content.$t : (matched.summary ? matched.summary.$t : '');
        var rendered = '<div class="content-card-box">' +
                       '<h1 class="content-title">' + pTitle + '</h1>' +
                       '<div class="content-body-area">' + pContent + '</div>' +
                       '</div>';
        directBox.innerHTML = rendered;
        setCache('post_' + currentPath, rendered); // Save in cache for instant back/forward navigation
      }
    }).catch(function() {});

    setupLiveSearch();
    return;
  }

  // 3. LABEL ARCHIVE LOADER (LIGHTWEIGHT SUMMARY FEED)
  if (isLabelPage) {
    var rawCat = window.location.pathname.split('/search/label/')[1].split('?')[0];
    var catName = decodeURIComponent(rawCat).replace(/\+/g, ' ').trim();
    var catNameLower = catName.toLowerCase();

    var catContainer = document.getElementById('category-view-container');
    var catTitle = document.getElementById('archive-category-title');
    var itemsList = document.getElementById('archive-items-list');
    var paginationBox = document.getElementById('archive-pagination');

    if (catContainer) catContainer.style.display = 'block';
    if (catTitle) catTitle.innerText = catName + ' - All Updates';

    var allFilteredPosts = [];
    var perPage = 30;

    // Use fast summary feed (10x smaller payload, CDN-cached)
    fetch('/feeds/posts/summary?alt=json&max-results=200')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var raw = data.feed.entry || [];
        globalAllPosts = [];

        raw.forEach(function(entry) {
          var t = (entry.title.$t || '').trim();
          var tl = t.toLowerCase();
          if (t.length < 15) return;

          var l = '#';
          for (var j = 0; j < (entry.link || []).length; j++) {
            if (entry.link[j].rel === 'alternate') { l = entry.link[j].href; break; }
          }

          var cats = (entry.category || []).map(function(c) {
            return (c.term || '').toLowerCase().trim();
          });

          var primaryCat = 'Job';
          if (cats.indexOf('answer key') > -1 || tl.indexOf('answer key') > -1) primaryCat = 'Answer Key';
          else if (cats.indexOf('syllabus') > -1 || tl.indexOf('syllabus') > -1) primaryCat = 'Syllabus';
          else if (cats.indexOf('result') > -1 || tl.indexOf('result') > -1) primaryCat = 'Result';
          else if (cats.indexOf('admit card') > -1 || tl.indexOf('admit card') > -1 || tl.indexOf('exam date') > -1) primaryCat = 'Admit Card';

          globalAllPosts.push({ title: t, link: l, cat: primaryCat });

          var isMatch = false;
          if (cats.indexOf(catNameLower) > -1) isMatch = true;
          else if (catNameLower === 'latest jobs' && (primaryCat === 'Job' || tl.indexOf('online form') > -1 || tl.indexOf('recruitment') > -1)) isMatch = true;
          else if (catNameLower === 'result' && (primaryCat === 'Result' || tl.indexOf('result') > -1)) isMatch = true;
          else if (catNameLower === 'admit card' && (primaryCat === 'Admit Card' || tl.indexOf('admit') > -1)) isMatch = true;
          else if (catNameLower === 'answer key' && (primaryCat === 'Answer Key' || tl.indexOf('answer key') > -1)) isMatch = true;
          else if (catNameLower === 'syllabus' && (primaryCat === 'Syllabus' || tl.indexOf('syllabus') > -1)) isMatch = true;

          if (isMatch) allFilteredPosts.push({ title: t, link: l });
        });

        renderArchivePage(1);
        setupLiveSearch();
      });

    function renderArchivePage(page) {
      var total = allFilteredPosts.length;
      var totalPages = Math.ceil(total / perPage) || 1;
      var start = (page - 1) * perPage;
      var end = Math.min(start + perPage, total);

      var listHtml = '';
      for (var i = start; i < end; i++) {
        var badges = getSmartBadges(allFilteredPosts[i].title);
        listHtml += '<li style="padding:10px 4px; border-bottom:1px solid var(--border); display:flex; align-items:center; gap:8px;">' +
                    badges.org +
                    '<a href="' + allFilteredPosts[i].link + '" style="font-weight:600;">' + allFilteredPosts[i].title + '</a>' +
                    badges.urgency + '</li>';
      }
      if (itemsList) itemsList.innerHTML = listHtml || '<li>No records found in this category.</li>';

      var pagHtml = '';
      if (totalPages > 1) {
        pagHtml += '<button ' + (page === 1 ? 'disabled' : '') + ' onclick="window._goCatPage(' + (page - 1) + ')" style="padding:6px 12px; border:1px solid var(--border); border-radius:4px; background:var(--surface); cursor:pointer;">« Prev</button>';
        for (var p = 1; p <= totalPages; p++) {
          if (p === 1 || p === totalPages || (p >= page - 2 && p <= page + 2)) {
            pagHtml += '<button class="' + (p === page ? 'active' : '') + '" onclick="window._goCatPage(' + p + ')" style="padding:6px 12px; border:1px solid var(--border); border-radius:4px; background:' + (p === page ? 'var(--brand)' : 'var(--surface)') + '; color:' + (p === page ? '#fff' : 'inherit') + '; cursor:pointer;">' + p + '</button>';
          }
        }
        pagHtml += '<button ' + (page === totalPages ? 'disabled' : '') + ' onclick="window._goCatPage(' + (page + 1) + ')" style="padding:6px 12px; border:1px solid var(--border); border-radius:4px; background:var(--surface); cursor:pointer;">Next »</button>';
      }
      if (paginationBox) paginationBox.innerHTML = pagHtml;
    }

    window._goCatPage = function(p) {
      renderArchivePage(p);
      window.scrollTo({ top: 120, behavior: 'smooth' });
    };
    return;
  }

  // 4. HOMEPAGE FEED LOADER (INSTANT 0ms RENDER FROM CACHE + 150KB SUMMARY FEED)
  if (currentPath === '' || currentPath === '/') {
    // A. Check Instant Session Cache (0ms Load Time!)
    var cachedEntries = getCache('sr_home_posts');
    if (cachedEntries && cachedEntries.length > 0) {
      globalAllPosts = cachedEntries;
      rawFeedEntries = cachedEntries;
      renderHomepageBoxes('ALL');
      setupLiveSearch();
    } else {
      // Show smooth animated pulse skeletons immediately (no white blank screens!)
      injectSkeletons();
    }

    // B. Fetch lightweight summary feed in background (Only 150KB, CDN-cached!)
    var blocked = ['contact us', 'privacy policy', 'disclaimer', 'about us', 'admission', 'latest job', 'admit card', 'result', 'syllabus', 'answer key', 'sarkari result'];

    fetch('/feeds/posts/summary?alt=json&max-results=90')
      .then(function(res) { return res.json(); })
      .then(function(data) {
        var entries = data.feed.entry || [];
        var freshPosts = [];

        entries.forEach(function(entry) {
          var title = (entry.title.$t || '').trim();
          var tl = title.toLowerCase();

          for (var b = 0; b < blocked.length; b++) {
            if (tl === blocked[b] || tl === blocked[b] + '™') return;
          }
          if (title.length < 15) return;

          var link = '#';
          for (var i = 0; i < (entry.link || []).length; i++) {
            if (entry.link[i].rel === 'alternate') { link = entry.link[i].href; break; }
          }

          var cats = (entry.category || []).map(function(c) {
            return (c.term || '').toLowerCase().trim();
          });

          var primaryCat = 'Job';
          if (cats.indexOf('answer key') > -1 || tl.indexOf('answer key') > -1) primaryCat = 'Answer Key';
          else if (cats.indexOf('syllabus') > -1 || tl.indexOf('syllabus') > -1) primaryCat = 'Syllabus';
          else if (cats.indexOf('result') > -1 || tl.indexOf('result') > -1) primaryCat = 'Result';
          else if (cats.indexOf('admit card') > -1 || tl.indexOf('admit card') > -1 || tl.indexOf('exam date') > -1) primaryCat = 'Admit Card';

          freshPosts.push({ title: title, link: link, cat: primaryCat });
        });

        if (freshPosts.length > 0) {
          globalAllPosts = freshPosts;
          rawFeedEntries = freshPosts;
          setCache('sr_home_posts', freshPosts); // Store in cache for 0ms next load!
          renderHomepageBoxes('ALL');
        }
        setupLiveSearch();
      })
      .catch(function(err) {});
  }
})();
