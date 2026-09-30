/* VectorWend: game logic. No build step, no backend. */
(function(){
  "use strict";
  var GAME_NAME = "VectorWend";
  var TZ = "America/Los_Angeles";
  // Puzzle #1 = Tuesday Sep 29, 2026 (civil date, Pacific time). New puzzles every Tue and Thu.
  var EPOCH_UTC = Date.UTC(2026, 8, 29);
  var DAY = 86400000;
  var NCOLORS = 6;

  var CLARKE_LINKS = {
    NATULAR:"https://www.clarke.com/mosquito-products/larvicides/natular-larvicide/",
    ALTOSID:"https://www.clarke.com/mosquito-products/larvicides/altosid-larvicide/",
    AQUABAC:"https://www.clarke.com/mosquito-products/larvicides/aquabac-bti-larvicide/",
    CENSOR:"https://www.clarke.com/mosquito-products/larvicides/censor/",
    COCOBEAR:"https://www.clarke.com/mosquito-products/larvicides/cocobear-larvicidal-oil/",
    DUPLEX:"https://www.clarke.com/mosquito-products/larvicides/duplex-larvicide/",
    FOURSTAR:"https://www.clarke.com/mosquito-products/larvicides/fourstar-larvicide/",
    ANVIL:"https://www.clarke.com/mosquito-products/adulticides/anvil-adulticide/",
    AQUAHALT:"https://www.clarke.com/mosquito-products/adulticides/aquahalt-adulticide/",
    BIOMIST:"https://www.clarke.com/mosquito-products/adulticides/biomist-adulticide/",
    CIELO:"https://www.clarke.com/mosquito-products/adulticides/cielo/",
    DUET:"https://www.clarke.com/mosquito-products/adulticides/duet-adulticide/",
    FLIT:"https://www.clarke.com/mosquito-products/adulticides/flit/",
    MERUS:"https://www.clarke.com/mosquito-products/adulticides/merus-3-0/",
    ZENIVEX:"https://www.clarke.com/mosquito-products/adulticides/zenivex-adulticide/"
  };
  var CAT_LABEL = {common:"Field term", challenging:"Expert term", clarke:"Clarke product"};

  var PUZZLES = window.WEND_PUZZLES || [];
  var WORDS = window.WEND_WORDS || {};

  // ---------- Date / schedule (America/Los_Angeles) ----------
  var fmt = new Intl.DateTimeFormat("en-US", {timeZone:TZ, year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit", hourCycle:"h23"});
  function laParts(ms){
    var o = {}; fmt.formatToParts(new Date(ms)).forEach(function(p){ o[p.type] = p.value; });
    return {y:+o.year, m:+o.month, d:+o.day, h:(+o.hour) % 24, mi:+o.minute, s:+o.second};
  }
  function dayIndexFromYMD(y, m, d){ return Math.round((Date.UTC(y, m - 1, d) - EPOCH_UTC) / DAY); }
  function dayIndexAt(ms){ var p = laParts(ms); return dayIndexFromYMD(p.y, p.m, p.d); }
  function puzzleForDayIndex(di){
    if (di < 0) return 1;
    var w = Math.floor(di / 7), dow = di % 7; // dow 0 = Tuesday, 2 = Thursday
    return w * 2 + (dow < 2 ? 0 : 1) + 1;
  }
  function dayIndexForPuzzle(n){ var k = n - 1; return Math.floor(k / 2) * 7 + [0, 2][k % 2]; }
  function ymdForDayIndex(di){ return new Date(EPOCH_UTC + di * DAY).toISOString().slice(0, 10); }
  function puzzleData(n){ return PUZZLES[(n - 1) % PUZZLES.length]; }
  function laMidnightMs(di){
    var civil = EPOCH_UTC + di * DAY, guess = civil + 8 * 3600000;
    for (var i = 0; i < 3; i++){
      var p = laParts(guess);
      var wall = Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi, p.s);
      guess = guess + (civil - wall);
    }
    return guess;
  }
  function prettyDate(di){
    return new Date(EPOCH_UTC + di * DAY).toLocaleDateString("en-US", {weekday:"short", month:"short", day:"numeric", timeZone:"UTC"});
  }

  var nowMs = function(){ return Date.now(); };
  var todayDI = dayIndexAt(nowMs());
  var PUZ = puzzleForDayIndex(todayDI);
  var P = puzzleData(PUZ);
  var R = P.rows, C = P.cols, GRID = P.grid, PW = P.words; // PW[i] = {w, path}
  var nextDI = dayIndexForPuzzle(PUZ + 1);
  var owner = new Array(R * C).fill(-1); // tile -> word index
  PW.forEach(function(wd, j){ wd.path.forEach(function(t){ owner[t] = j; }); });

  // ---------- Storage ----------
  var KS = "vectorwend-state-v1", KT = "vectorwend-stats-v1", KH = "vectorwend-seen-help";
  function load(k, def){ try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch(e){ return def; } }
  function save(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }
  var sig = GRID + "|" + PW.map(function(w){ return w.w; }).join(",");
  var state = load(KS, null);
  if (!state || state.puzzle !== PUZ || state.sig !== sig){
    state = {puzzle:PUZ, sig:sig, found:[], reveal:PW.map(function(){ return 0; }), hinted:PW.map(function(){ return false; }), hints:0, elapsed:0, status:"playing"};
    save(KS, state);
  }
  var stats = load(KT, {played:0, streak:0, maxStreak:0, best:null, total:0, noHint:0, lastWin:null, lastCounted:null});

  // ---------- Helpers ----------
  function pad(n){ return (n < 10 ? "0" : "") + n; }
  function fmtTime(ms){
    var s = Math.floor(ms / 1000), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), ss = s % 60;
    return h ? h + ":" + pad(m) + ":" + pad(ss) : m + ":" + pad(ss);
  }
  function isFound(j){ return state.found.indexOf(j) >= 0; }
  function adjacent(a, b){ var ar = Math.floor(a / C), ac = a % C, br = Math.floor(b / C), bc = b % C; return Math.abs(ar - br) + Math.abs(ac - bc) === 1; }
  function sameSet(a, b){ if (a.length !== b.length) return false; var s = {}; a.forEach(function(x){ s[x] = 1; }); return b.every(function(x){ return s[x]; }); }
  function siteUrl(){ return location.href.split(/[?#]/)[0]; }
  function shareText(){
    var hints = state.hints;
    var row = PW.map(function(_, j){ return state.hinted[j] ? "\uD83D\uDFE8" : "\uD83D\uDFE9"; }).join("");
    return GAME_NAME + " #" + PUZ + " \uD83E\uDD9F\nSolved in " + fmtTime(state.elapsed) + " | " + hints + (hints === 1 ? " hint" : " hints") + "\n" + row + "\n" + siteUrl();
  }

  // ---------- DOM ----------
  var $ = function(id){ return document.getElementById(id); };
  var gridEl = $("grid"), wrapEl = $("grid-wrap"), linesEl = $("lines"), slotsEl = $("slots");
  var tiles = [];
  var root = document.documentElement;
  root.style.setProperty("--cols", C); root.style.setProperty("--rows", R);
  $("chip-num").textContent = "Puzzle #" + PUZ;
  $("chip-words").textContent = PW.length + " words";
  $("chip-date").textContent = prettyDate(dayIndexForPuzzle(PUZ));
  var preview = document.createElement("div"); preview.className = "preview"; preview.hidden = true; wrapEl.appendChild(preview);

  function buildGrid(){
    gridEl.innerHTML = "";
    for (var i = 0; i < R * C; i++){
      var t = document.createElement("div");
      t.className = "gtile" + (GRID[i] === "#" ? " wall" : "");
      t.dataset.i = i;
      t.setAttribute("role", "gridcell");
      if (GRID[i] !== "#"){ t.textContent = GRID[i]; t.setAttribute("aria-label", GRID[i]); } else t.setAttribute("aria-label", "wall");
      gridEl.appendChild(t); tiles.push(t);
    }
  }
  function buildSlots(){
    slotsEl.innerHTML = "";
    PW.forEach(function(wd, j){
      var s = document.createElement("div"); s.className = "slot"; s.dataset.j = j;
      s.setAttribute("aria-label", wd.w.length + "-letter word");
      for (var k = 0; k < wd.w.length; k++){ var b = document.createElement("div"); b.className = "sl"; s.appendChild(b); }
      slotsEl.appendChild(s);
    });
  }
  function colorOf(j){ return "c" + (j % NCOLORS); }
  function center(i){ var t = tiles[i]; return [t.offsetLeft + t.offsetWidth / 2, t.offsetTop + t.offsetHeight / 2]; }
  function polyline(path, color, width, opacity){
    var pts = path.map(function(i){ return center(i).join(","); }).join(" ");
    return '<polyline points="' + pts + '" fill="none" stroke="' + color + '" stroke-width="' + width + '" stroke-linecap="round" stroke-linejoin="round" opacity="' + opacity + '"/>';
  }
  var CSSCOL = ["#2e8b57", "#0b6fa4", "#c98a0e", "#7a5cb0", "#138f8a", "#cf5f36"];
  var trace = [], dragging = false, badTimer = null;
  function render(){
    var hintTile = {};
    PW.forEach(function(wd, j){ if (!isFound(j)) for (var k = 0; k < state.reveal[j]; k++) hintTile[wd.path[k]] = k + 1; });
    tiles.forEach(function(t, i){
      if (GRID[i] === "#") return;
      var j = owner[i], f = isFound(j);
      t.className = "gtile" + (f ? " found " + colorOf(j) : "") + (trace.indexOf(i) >= 0 ? " sel" : "") + (hintTile[i] ? " hint" : "");
      var hn = t.querySelector(".hn");
      if (hintTile[i] && !f){ if (!hn){ hn = document.createElement("span"); hn.className = "hn"; t.appendChild(hn); } hn.textContent = hintTile[i]; }
      else if (hn) hn.remove();
    });
    PW.forEach(function(wd, j){
      var s = slotsEl.children[j], f = isFound(j);
      s.className = "slot" + (f ? " done" : "") + (s.classList.contains("pop") ? " pop" : "");
      for (var k = 0; k < wd.w.length; k++){
        var b = s.children[k];
        var show = f || k < state.reveal[j];
        b.textContent = show ? wd.w[k] : "";
        b.className = "sl" + (f ? " " + colorOf(j) : (show ? " rev" : ""));
      }
    });
    drawLines();
    var over = state.status !== "playing";
    $("btn-hint").disabled = over; $("btn-undo").disabled = over || !state.found.length; $("btn-reset").disabled = over || !state.found.length;
  }
  function drawLines(){
    var w = gridEl.offsetWidth, h = gridEl.offsetHeight, tile = tiles[0] ? tiles[0].offsetWidth : 40;
    linesEl.setAttribute("viewBox", "0 0 " + w + " " + h);
    var svg = "";
    // drawn beneath the tiles: shows as connectors in the gaps between tiles
    state.found.forEach(function(j){ svg += polyline(PW[j].path, CSSCOL[j % NCOLORS], Math.max(8, tile * 0.34), 1); });
    if (trace.length > 1) svg += polyline(trace, "#1b7f74", Math.max(8, tile * 0.34), 0.9);
    linesEl.innerHTML = svg;
  }
  function toast(msg, ms){
    var w = $("toast-wrap"), t = document.createElement("div"); t.className = "toast"; t.textContent = msg; w.appendChild(t);
    setTimeout(function(){ t.classList.add("hide"); setTimeout(function(){ t.remove(); }, 350); }, ms || 1500);
  }

  // ---------- Fit to viewport ----------
  function fit(){
    var gap = parseFloat(getComputedStyle(root).getPropertyValue("--gap")) || 6;
    root.style.setProperty("--tile", "40px");
    var bs = document.body.style; bs.height = "auto"; bs.minHeight = "0";
    var chrome = document.body.offsetHeight - gridEl.offsetHeight;
    bs.height = ""; bs.minHeight = "";
    var availH = window.innerHeight - chrome - 6;
    var byH = (availH - (R - 1) * gap) / R;
    var byW = (Math.min(window.innerWidth, 560) - 28 - (C - 1) * gap) / C;
    var t = Math.floor(Math.max(34, Math.min(66, byW, byH)));
    root.style.setProperty("--tile", t + "px");
    drawLines();
  }

  // ---------- Input: drag through tiles (pointer events cover mouse, touch and pen) ----------
  function tileAt(x, y){
    var el = document.elementFromPoint(x, y);
    var t = el && el.closest ? el.closest(".gtile") : null;
    if (!t || !gridEl.contains(t)) return -1;
    var i = +t.dataset.i, r = t.getBoundingClientRect();
    // only count the inner part of a tile so cutting corners doesn't grab a neighbour
    var dx = x - (r.left + r.width / 2), dy = y - (r.top + r.height / 2);
    if (Math.abs(dx) > r.width * 0.42 || Math.abs(dy) > r.height * 0.42) return -1;
    return i;
  }
  function usable(i){ return i >= 0 && GRID[i] !== "#" && !isFound(owner[i]); }
  function showPreview(){
    if (trace.length){ preview.textContent = trace.map(function(i){ return GRID[i]; }).join(""); preview.hidden = false; }
    else preview.hidden = true;
  }
  function blocked(){ return state.status !== "playing" || !!document.querySelector(".modal:not([hidden])"); }
  function onDown(e){
    if (blocked()) return;
    var i = tileAt(e.clientX, e.clientY);
    if (!usable(i)) return;
    e.preventDefault();
    clearBad();
    dragging = true; trace = [i];
    try { gridEl.setPointerCapture(e.pointerId); } catch(err){}
    render(); showPreview();
  }
  function onMove(e){
    if (!dragging) return;
    e.preventDefault();
    var i = tileAt(e.clientX, e.clientY);
    if (i < 0 || i === trace[trace.length - 1]) return;
    if (trace.length > 1 && i === trace[trace.length - 2]){ trace.pop(); render(); showPreview(); return; } // back up
    if (trace.indexOf(i) >= 0 || !usable(i) || !adjacent(trace[trace.length - 1], i)) return;
    trace.push(i); render(); showPreview();
  }
  function onUp(e){
    if (!dragging) return;
    dragging = false;
    try { gridEl.releasePointerCapture(e.pointerId); } catch(err){}
    var path = trace.slice();
    preview.hidden = true;
    if (path.length < 2){ trace = []; render(); return; }
    submit(path);
  }
  gridEl.addEventListener("pointerdown", onDown);
  gridEl.addEventListener("pointermove", onMove);
  gridEl.addEventListener("pointerup", onUp);
  gridEl.addEventListener("pointercancel", onUp);
  gridEl.addEventListener("touchmove", function(e){ e.preventDefault(); }, {passive:false}); // stop iOS scroll/bounce while tracing
  gridEl.addEventListener("contextmenu", function(e){ e.preventDefault(); });

  function clearBad(){ if (badTimer){ clearTimeout(badTimer); badTimer = null; } tiles.forEach(function(t){ t.classList.remove("bad"); }); gridEl.classList.remove("shake"); }
  function reject(path, msg){
    trace = []; render();
    path.forEach(function(i){ tiles[i].classList.add("bad"); });
    gridEl.classList.remove("shake"); void gridEl.offsetWidth; gridEl.classList.add("shake");
    if (msg) toast(msg);
    badTimer = setTimeout(clearBad, 550);
  }
  function submit(path){
    var word = path.map(function(i){ return GRID[i]; }).join("");
    var hit = -1, wordMatch = -1;
    PW.forEach(function(wd, j){
      if (isFound(j) || wd.w !== word) return;
      wordMatch = j;
      if (sameSet(wd.path, path)) hit = j; // same word on the intended tiles (order among repeated letters doesn't matter)
    });
    if (hit >= 0){ trace = []; solve(hit, true); return; }
    if (wordMatch >= 0) return reject(path, "Right word, wrong tiles");
    if (path.length < 3) return reject(path, null);
    reject(path, "Not one of the hidden words");
  }
  function solve(j, byPlayer){
    state.found.push(j); ensureTimer();
    if (state.found.length === PW.length){ state.status = "won"; accumulate(); }
    save(KS, state);
    var s = slotsEl.children[j]; s.classList.remove("pop"); void s.offsetWidth; s.classList.add("pop");
    render();
    if (state.status === "won") finish(true);
    else if (byPlayer) toast(["Nice!", "Got it!", "Found!", "Great trace!"][state.found.length % 4], 900);
  }

  // ---------- Hint / Undo / Reset ----------
  function hint(){
    if (blocked()) return;
    var target = -1;
    PW.forEach(function(wd, j){ if (target < 0 && !isFound(j) && state.reveal[j] > 0) target = j; });
    if (target < 0) PW.forEach(function(wd, j){ if (target < 0 && !isFound(j)) target = j; });
    if (target < 0) return;
    state.reveal[target]++; state.hints++; state.hinted[target] = true;
    if (state.reveal[target] >= PW[target].w.length){ solve(target, false); return; }
    save(KS, state); render();
    toast(state.reveal[target] === 1 ? "Start tile highlighted" : "Next letter revealed", 1100);
  }
  function undo(){
    if (blocked() || !state.found.length) return;
    state.found.pop(); save(KS, state); render();
  }
  function reset(){
    if (blocked() || !state.found.length) return;
    state.found = []; save(KS, state); render(); toast("Board cleared", 1000);
  }
  $("btn-hint").addEventListener("click", hint);
  $("btn-undo").addEventListener("click", undo);
  $("btn-reset").addEventListener("click", reset);

  // ---------- Timer (runs while playing, tab visible and no dialog open) ----------
  var lastTick = null;
  function running(){ return state.status === "playing" && !document.hidden && !document.querySelector(".modal:not([hidden])"); }
  function accumulate(){ var n = nowMs(); if (lastTick !== null) state.elapsed += Math.max(0, Math.min(n - lastTick, 5000)); lastTick = running() ? n : null; }
  function ensureTimer(){ if (lastTick === null && running()) lastTick = nowMs(); }
  var saveCounter = 0;
  function timerTick(){
    if (state.status === "playing"){ accumulate(); ensureTimer(); if (++saveCounter % 8 === 0) save(KS, state); }
    $("chip-time").textContent = fmtTime(state.elapsed);
  }
  document.addEventListener("visibilitychange", function(){ accumulate(); ensureTimer(); save(KS, state); });
  window.addEventListener("pagehide", function(){ accumulate(); save(KS, state); });

  // ---------- Finish / stats ----------
  function finish(fresh){
    if (fresh && stats.lastCounted !== PUZ){
      stats.played++; stats.lastCounted = PUZ;
      stats.streak = (stats.lastWin === PUZ - 1) ? stats.streak + 1 : 1;
      stats.lastWin = PUZ; stats.maxStreak = Math.max(stats.maxStreak, stats.streak);
      stats.total = (stats.total || 0) + state.elapsed;
      if (state.hints === 0){ stats.noHint = (stats.noHint || 0) + 1; if (stats.best === null || state.elapsed < stats.best) stats.best = state.elapsed; }
      save(KT, stats);
    }
    $("chip-time").textContent = fmtTime(state.elapsed);
    if (fresh){
      gridEl.classList.add("win");
      toast(state.hints ? "Solved!" : "Flawless!", 1300);
      setTimeout(openStats, 1400);
    }
  }

  // ---------- Modals ----------
  function openModal(id){ accumulate(); $(id).hidden = false; }
  function closeModal(el){ el.hidden = true; ensureTimer(); }
  document.querySelectorAll(".modal").forEach(function(m){
    m.addEventListener("click", function(e){ if (e.target === m || e.target.closest("[data-close]")){ closeModal(m); if (m.id === "modal-help") save(KH, true); } });
  });
  $("btn-help").addEventListener("click", function(){ openModal("modal-help"); });
  $("btn-stats").addEventListener("click", openStats);
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[c]; }); }
  function openStats(){
    var done = state.status === "won";
    $("st-played").textContent = stats.played;
    $("st-streak").textContent = stats.streak;
    $("st-max").textContent = stats.maxStreak;
    $("st-best").textContent = stats.best === null ? "-" : fmtTime(stats.best);
    $("st-extra").textContent = stats.played ? ("Average time " + fmtTime((stats.total || 0) / stats.played) + " \u00B7 " + (stats.noHint || 0) + " solved without hints") : "Best time counts hint-free solves.";
    $("result-block").hidden = !done; $("end-actions").hidden = !done; $("words-block").hidden = !done;
    $("countdown-inline").hidden = done;
    if (done){
      $("result-title").textContent = state.hints ? "Solved!" : "Solved with no hints!";
      $("result-sub").textContent = "Puzzle #" + PUZ + " \u00B7 " + prettyDate(dayIndexForPuzzle(PUZ));
      $("res-time").textContent = fmtTime(state.elapsed);
      $("res-hints").textContent = state.hints;
      $("res-theme").textContent = "Theme: " + P.theme;
      $("word-list").innerHTML = PW.map(function(wd, j){
        var info = WORDS[wd.w] || ["common", ""];
        var link = info[0] === "clarke" && CLARKE_LINKS[wd.w] ? '<div><a href="' + CLARKE_LINKS[wd.w] + '" target="_blank" rel="noopener">Learn more on clarke.com &rarr;</a></div>' : "";
        return '<div class="wcard" style="border-left-color:' + CSSCOL[j % NCOLORS] + '"><div class="wtop"><span class="ww">' + esc(wd.w) + '</span>' +
          '<span class="answer-cat ' + esc(info[0]) + '">' + esc(CAT_LABEL[info[0]] || info[0]) + '</span>' +
          (state.hinted[j] ? '<span class="wh" title="Hint used">\uD83D\uDCA1</span>' : '') + '</div>' +
          '<div class="wd">' + esc(info[1]) + '</div>' + link + '</div>';
      }).join("");
    }
    tick();
    openModal("modal-stats");
  }
  function tick(){
    var ms = Math.max(0, laMidnightMs(nextDI) - nowMs());
    var h = Math.floor(ms / 3600000), m = Math.floor(ms % 3600000 / 60000), s = Math.floor(ms % 60000 / 1000);
    var txt = pad(h) + ":" + pad(m) + ":" + pad(s);
    $("countdown").textContent = txt;
    $("next-date").textContent = "#" + (PUZ + 1) + " on " + prettyDate(nextDI) + " (PT)";
    $("countdown-inline").textContent = "Next puzzle (#" + (PUZ + 1) + ", " + prettyDate(nextDI) + ") in " + txt;
  }
  setInterval(function(){
    timerTick(); tick();
    if (dayIndexAt(nowMs()) >= nextDI && state.status !== "playing" && !document.hidden) location.reload();
  }, 250);

  // ---------- Share ----------
  function copyText(text){
    if (navigator.clipboard && window.isSecureContext){
      return navigator.clipboard.writeText(text).then(function(){ return true; }, function(){ return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }
  function legacyCopy(text){
    var ta = document.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select(); var ok = false; try { ok = document.execCommand("copy"); } catch(e){} ta.remove(); return ok;
  }
  var isMobile = (window.matchMedia && matchMedia("(pointer:coarse)").matches) || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  $("btn-share").addEventListener("click", function(){
    var text = shareText();
    if (isMobile && navigator.share){
      navigator.share({text:text}).catch(function(err){ if (!err || err.name !== "AbortError") copyText(text).then(function(ok){ toast(ok ? "Result copied to clipboard" : "Couldn't copy"); }); });
    } else {
      copyText(text).then(function(ok){ toast(ok ? "Result copied to clipboard" : "Couldn't copy. Select and copy manually."); });
    }
  });
  $("btn-linkedin").addEventListener("click", function(){
    var text = shareText();
    var url = "https://www.linkedin.com/feed/?shareActive=true&text=" + encodeURIComponent(text);
    var w = null; try { w = window.open(url, "_blank"); } catch(e){}
    if (w){ try { w.opener = null; } catch(e){} }
    copyText(text).then(function(ok){
      if (!w) toast(ok ? "Pop-up blocked. Result copied, so paste it into a LinkedIn post." : "Pop-up blocked. Couldn't copy.", 3000);
      else if (ok) toast("Result also copied, in case LinkedIn doesn't prefill it", 2600);
    });
  });
  document.addEventListener("keydown", function(e){
    var open = document.querySelector(".modal:not([hidden])");
    if (e.key === "Escape" && open) closeModal(open);
  });

  // ---------- Init ----------
  buildGrid(); buildSlots();
  fit(); render();
  window.addEventListener("resize", fit);
  if (window.ResizeObserver) new ResizeObserver(drawLines).observe(gridEl);
  if (state.status === "won"){ finish(false); setTimeout(openStats, 300); }
  else if (!load(KH, false)) openModal("modal-help");
  ensureTimer(); timerTick();

  // Expose helpers for testing / debugging.
  window.VW = {puzzleForDayIndex:puzzleForDayIndex, dayIndexForPuzzle:dayIndexForPuzzle, dayIndexFromYMD:dayIndexFromYMD,
    dayIndexAt:dayIndexAt, ymdForDayIndex:ymdForDayIndex, puzzleData:puzzleData, laMidnightMs:laMidnightMs,
    shareText:shareText, puzzle:PUZ, count:PUZZLES.length,
    getState:function(){ return JSON.parse(JSON.stringify(state)); }, getStats:function(){ return JSON.parse(JSON.stringify(stats)); }};
})();
