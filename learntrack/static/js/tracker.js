/*
 * LearnTrack clickstream tracker.
 *
 * Collects interaction events in the browser, queues them and posts them in
 * batches to POST /api/events. Loaded on every page for logged-in users.
 *
 * Public API (used by lesson.js):
 *   LearnTrack.track(eventName, action, {component, context, metadata})
 *   LearnTrack.post(url, body)  -> Promise<json>   (adds the CSRF header)
 */
(function () {
  'use strict';

  var body = document.body;
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var defaultContext = body.dataset.context || 'LearnTrack';
  var defaultComponent = body.dataset.component || 'System';
  var FLUSH_MS = 2000;
  var MAX_QUEUE = 10;

  var queue = [];
  var timer = null;
  var sentCount = 0;
  var pageStart = Date.now();
  var hiddenAt = null;
  var hiddenTotal = 0;
  var maxScroll = 0;
  var leaving = false;
  var exitTracked = false;

  function clip(text, max) {
    text = String(text || '').replace(/\s+/g, ' ').trim();
    return text.length > max ? text.slice(0, max - 1) + '…' : text;
  }

  function track(eventName, action, options) {
    options = options || {};
    queue.push({
      event_name: eventName,
      action: action,
      component: options.component || defaultComponent,
      context: options.context || defaultContext,
      metadata: options.metadata || {},
      page_url: location.pathname + location.search,
      ts: new Date().toISOString()
    });
    updateBadge(eventName);
    if (queue.length >= MAX_QUEUE) flush();
    else if (!timer) timer = setTimeout(flush, FLUSH_MS);
  }

  function flush(leaving) {
    clearTimeout(timer);
    timer = null;
    if (!queue.length) return Promise.resolve();
    var batch = queue.splice(0, queue.length);
    var payload = JSON.stringify({ events: batch, csrf_token: csrf });
    // While the page is unloading a normal request may be cancelled, so use a beacon.
    if (leaving === true && navigator.sendBeacon) {
      navigator.sendBeacon('/api/events', new Blob([payload], { type: 'application/json' }));
      return Promise.resolve();
    }
    return fetch('/api/events', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: payload
    }).catch(function () {
      // Network hiccup: put the batch back and try again on the next flush.
      if (queue.length < 200) queue = batch.concat(queue);
    });
  }

  function post(url, data) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      body: JSON.stringify(data || {})
    }).then(function (res) {
      return res.json().then(function (json) {
        if (!res.ok) throw new Error(json.error || 'Request failed');
        return json;
      });
    });
  }

  /* ---- small on-page indicator so learners can see tracking happen ---- */
  function updateBadge(eventName) {
    sentCount += 1;
    var count = document.getElementById('live-count');
    var last = document.getElementById('live-last');
    if (count) count.textContent = sentCount;
    if (last) last.textContent = '· last: ' + eventName;
  }

  /* ---- clicks ---- */
  function describeElement(el) {
    var tag = el.tagName.toLowerCase();
    var label = el.dataset.trackLabel || el.getAttribute('aria-label');
    if (!label && (tag === 'input' || tag === 'select' || tag === 'textarea')) {
      // Never read what was typed: identify fields by name and type only.
      label = (el.name || el.id || tag) + ' field' + (el.type ? ' (' + el.type + ')' : '');
    }
    if (!label && (el.children.length > 2 || el.textContent.length > 120)) {
      // A large container (card, section, page background): name it instead of quoting all its text.
      label = tag + (el.id ? '#' + el.id : el.classList.length ? '.' + el.classList[0] : '');
    }
    return { tag: tag, label: clip(label || el.textContent || el.id || tag, 70) };
  }

  document.addEventListener('click', function (event) {
    var target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    // Video controls and quiz/check options emit their own, richer events.
    if (target.closest('video') || target.closest('[data-no-track]')) return;
    var el = target.closest('a, button, input, select, textarea, label, [data-track-label]') || target;
    var info = describeElement(el);
    var isLink = info.tag === 'a';
    var isButton = info.tag === 'button' || (info.tag === 'input' && /submit|button/.test(el.type));
    var name = isLink ? 'Link clicked' : isButton ? 'Button clicked' : 'Element clicked';
    var kind = isLink ? 'link' : isButton ? 'button' : '<' + info.tag + '> element';
    var href = isLink ? el.getAttribute('href') : null;
    track(name, 'clicked ' + kind + " '" + info.label + "'" + (href ? ' (to ' + clip(href, 80) + ')' : ''), {
      metadata: {
        tag: info.tag, id: el.id || null, classes: clip(el.className, 80) || null, label: info.label,
        href: href, x: Math.round(event.pageX), y: Math.round(event.pageY),
        viewport: window.innerWidth + 'x' + window.innerHeight
      }
    });
  }, true);

  /* ---- form submissions (which form, never its contents) ---- */
  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (form.closest('[data-no-track]') || form.id === 'quiz-form') return;
    track('Form submitted', "submitted form '" + (form.id || form.getAttribute('action') || 'form') + "'", {
      metadata: { form_id: form.id || null, action: form.getAttribute('action'), method: form.method }
    });
    if (form.hasAttribute('data-flush-first')) {
      // Logging out ends the session, so the last events must be stored before the form is sent.
      event.preventDefault();
      trackExit();
      exitTracked = true;
      flush().then(function () { form.submit(); }, function () { form.submit(); });
      return;
    }
    flush(true);
  }, true);

  /* ---- scroll depth: 25 / 50 / 75 / 100 % ---- */
  var reached = {};
  var scrollPending = false;
  function checkScroll() {
    scrollPending = false;
    var doc = document.documentElement;
    if (doc.scrollHeight <= window.innerHeight + 40) return; // page does not scroll
    var percent = Math.min(100, Math.round(100 * (window.scrollY + window.innerHeight) / doc.scrollHeight));
    maxScroll = Math.max(maxScroll, percent);
    [25, 50, 75, 100].forEach(function (mark) {
      if (percent >= mark && !reached[mark]) {
        reached[mark] = true;
        if (window.scrollY > 0) {
          track('Page scrolled', 'scrolled to ' + mark + '% of the page', { metadata: { depth_percent: mark } });
        }
      }
    });
  }
  window.addEventListener('scroll', function () {
    if (!scrollPending) { scrollPending = true; setTimeout(checkScroll, 250); }
  }, { passive: true });

  /* ---- attention: tab hidden / visible ---- */
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      if (leaving) return;   // navigating away is reported as "Page exited", not as a hidden tab
      hiddenAt = Date.now();
      track('Tab hidden', 'switched away from the page', { metadata: { seconds_on_page: secondsOnPage() } });
    } else if (hiddenAt) {
      var away = Math.round((Date.now() - hiddenAt) / 1000);
      hiddenTotal += Date.now() - hiddenAt;
      hiddenAt = null;
      track('Tab visible', 'returned to the page after ' + away + 's away', { metadata: { seconds_away: away } });
    }
  });

  /* ---- copying text (length only) ---- */
  document.addEventListener('copy', function () {
    var length = String(window.getSelection() || '').length;
    if (length) track('Text copied', 'copied ' + length + ' characters of text', { metadata: { characters: length } });
  });

  /* ---- leaving the page ---- */
  function secondsOnPage() { return Math.round((Date.now() - pageStart) / 1000); }
  function trackExit() {
    var total = secondsOnPage();
    track('Page exited', 'left the page after ' + total + 's', {
      metadata: {
        seconds_on_page: total,
        seconds_visible: Math.max(0, Math.round((Date.now() - pageStart - hiddenTotal) / 1000)),
        max_scroll_percent: maxScroll
      }
    });
  }
  window.addEventListener('pagehide', function () {
    leaving = true;
    if (exitTracked) return;
    // Some browsers fire visibilitychange just before pagehide; drop that duplicate.
    var lastQueued = queue[queue.length - 1];
    if (lastQueued && lastQueued.event_name === 'Tab hidden' && Date.now() - hiddenAt < 300) {
      queue.pop();
      sentCount -= 1;
      hiddenAt = null;
    }
    trackExit();
    flush(true);
  });

  window.addEventListener('pageshow', function (event) {
    leaving = false;
    exitTracked = false;
    if (event.persisted) { pageStart = Date.now(); hiddenTotal = 0; }  // restored from the back/forward cache
  });

  /* ---- show stored UTC timestamps in the viewer's local time ---- */
  document.querySelectorAll('time.js-time').forEach(function (el) {
    var date = new Date(el.getAttribute('datetime'));
    if (isNaN(date)) return;
    var full = el.dataset.format === 'full';
    el.textContent = date.toLocaleString(undefined, full
      ? { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }
      : { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
    el.title = el.getAttribute('datetime') + ' (UTC)';
  });

  window.LearnTrack = { track: track, flush: flush, post: post };
})();
