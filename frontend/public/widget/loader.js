(function () {
  'use strict';

  var VISITOR_KEY = 'chatmedbot:visitor';
  var BTN_ID = 'chatmedbot-launcher';
  var FRAME_ID = 'chatmedbot-frame';
  var BADGE_ID = 'chatmedbot-badge';
  var SVG_NS = 'http://www.w3.org/2000/svg';

  function getOrCreateVisitorId() {
    var id = localStorage.getItem(VISITOR_KEY);
    if (!id) {
      id = ([1e7] + -1e3 + -4e3 + -8e3 + -1e11).replace(/[018]/g, function (c) {
        return (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16);
      });
      localStorage.setItem(VISITOR_KEY, id);
    }
    return id;
  }

  function getScriptOrigin() {
    var scripts = document.querySelectorAll('script[data-key]');
    for (var i = 0; i < scripts.length; i++) {
      var src = scripts[i].src || '';
      if (src.indexOf('loader.js') !== -1) {
        try { return new URL(src).origin; } catch (e) { return ''; }
      }
    }
    return window.location.origin;
  }

  function makeSvg(paths) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('width', '26');
    svg.setAttribute('height', '26');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', '#fff');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    paths.forEach(function (attrs) {
      var tag = attrs.tag || 'path';
      var el = document.createElementNS(SVG_NS, tag);
      Object.keys(attrs).forEach(function (k) {
        if (k !== 'tag') el.setAttribute(k, attrs[k]);
      });
      svg.appendChild(el);
    });
    return svg;
  }

  function chatSvg() {
    return makeSvg([{ d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' }]);
  }

  function closeSvg() {
    return makeSvg([
      { tag: 'line', x1: '18', y1: '6', x2: '6', y2: '18' },
      { tag: 'line', x1: '6', y1: '6', x2: '18', y2: '18' }
    ]);
  }

  function makeBadge() {
    var badge = document.createElement('span');
    badge.id = BADGE_ID;
    badge.style.cssText = 'position:absolute;top:-4px;right:-4px;background:#ef4444;color:#fff;font-size:10px;font-weight:700;border-radius:99px;min-width:18px;height:18px;display:none;align-items:center;justify-content:center;padding:0 4px;';
    return badge;
  }

  function init() {
    var script = document.currentScript
      || (function () {
        var all = document.querySelectorAll('script[data-key]');
        return all[all.length - 1];
      })();

    var apiKey = script && script.getAttribute('data-key');
    if (!apiKey) { console.warn('[ChatMedBot] data-key is required'); return; }

    var origin = getScriptOrigin();
    var visitorId = getOrCreateVisitorId();

    fetch(origin + '/api/v1/widget/config?key=' + encodeURIComponent(apiKey))
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (cfg) { render(cfg, apiKey, visitorId, origin); })
      .catch(function (e) { console.warn('[ChatMedBot] failed to load config', e); });
  }

  function render(cfg, apiKey, visitorId, origin) {
    var s = cfg.settings || {};
    var color = s.primary_color || '#3B82F6';
    var position = s.position || 'bottom-right';
    var isRight = position !== 'bottom-left';

    var hPos = isRight ? 'right:20px' : 'left:20px';
    var fPos = isRight ? 'right:16px' : 'left:16px';

    if (!document.getElementById('chatmedbot-style')) {
      var style = document.createElement('style');
      style.id = 'chatmedbot-style';
      var css = [
        '#' + BTN_ID + '{position:fixed;bottom:20px;' + hPos + ';width:56px;height:56px;border-radius:50%;background:' + color + ';border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.18);z-index:2147483000;display:flex;align-items:center;justify-content:center;transition:transform .15s,box-shadow .15s;outline:none;}',
        '#' + BTN_ID + ':hover{transform:scale(1.08);box-shadow:0 8px 24px rgba(0,0,0,.22);}',
        '#' + FRAME_ID + '{position:fixed;bottom:86px;' + fPos + ';width:380px;max-width:calc(100vw - 32px);height:600px;max-height:calc(100vh - 110px);border:none;border-radius:20px;box-shadow:0 16px 48px rgba(0,0,0,.18);z-index:2147483001;display:none;overflow:hidden;}',
        '@media(max-width:480px){#' + FRAME_ID + '{width:100vw;max-width:100vw;height:100vh;max-height:100vh;bottom:0;right:0!important;left:0!important;border-radius:0;}}'
      ].join('');
      style.textContent = css;
      document.head.appendChild(style);
    }

    var btn = document.createElement('button');
    btn.id = BTN_ID;
    btn.setAttribute('aria-label', 'Открыть чат');
    btn.style.position = 'relative';
    var currentSvg = chatSvg();
    btn.appendChild(currentSvg);
    var badge = makeBadge();
    btn.appendChild(badge);
    document.body.appendChild(btn);

    var frame = document.createElement('iframe');
    frame.id = FRAME_ID;
    frame.allow = 'clipboard-write';
    frame.src = origin + '/widget/embed?key=' + encodeURIComponent(apiKey) + '&v=' + encodeURIComponent(visitorId);
    document.body.appendChild(frame);

    var isOpen = false;

    function setIcon(svgNode) {
      var old = btn.querySelector('svg');
      if (old) btn.removeChild(old);
      btn.insertBefore(svgNode, btn.firstChild);
    }

    function open() {
      isOpen = true;
      frame.style.display = 'block';
      btn.setAttribute('aria-label', 'Закрыть чат');
      setIcon(closeSvg());
      badge.style.display = 'none';
    }

    function close() {
      isOpen = false;
      frame.style.display = 'none';
      btn.setAttribute('aria-label', 'Открыть чат');
      setIcon(chatSvg());
    }

    btn.addEventListener('click', function () {
      isOpen ? close() : open();
    });

    window.addEventListener('message', function (e) {
      if (e.source !== frame.contentWindow) return;
      if (!e.data || typeof e.data !== 'object') return;
      if (e.data.type === 'chatmedbot:close') close();
      if (e.data.type === 'chatmedbot:unread' && !isOpen) {
        var n = e.data.count || 0;
        badge.textContent = n > 9 ? '9+' : String(n);
        badge.style.display = n > 0 ? 'flex' : 'none';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
