"""Headless tests for VectorWend. Run: python tools/test_game.py (needs playwright + chromium).
Screenshots use a FUTURE puzzle (#39, Tue Feb 9 2027) so no live answers leak."""
import datetime as dt, pathlib, subprocess, sys, time, urllib.parse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
LA = ZoneInfo("America/Los_Angeles")
import socket
_s = socket.socket(); _s.bind(("127.0.0.1", 0)); PORT = _s.getsockname()[1]; _s.close()
fails = []
def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)

srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(0.8)
URL = f"http://127.0.0.1:{PORT}/index.html"
def la(y, m, d, h=12, mi=0): return dt.datetime(y, m, d, h, mi, tzinfo=LA)

errors = []
def open_page(browser, when, url=URL, install=False, **ctx):
    c = browser.new_context(**ctx)
    p = c.new_page()
    p.on("pageerror", lambda e: errors.append(str(e)))
    if install: p.clock.install(time=when)
    else: p.clock.set_fixed_time(when)
    p.goto(url)
    p.wait_for_function("window.VW !== undefined")
    return c, p

def close_modals(p):
    p.evaluate("document.querySelectorAll('.modal').forEach(m=>m.hidden=true)")

def centers(p):
    return p.evaluate("Array.from(document.querySelectorAll('#grid .gtile')).map(t=>{const r=t.getBoundingClientRect();return [r.left+r.width/2, r.top+r.height/2]})")

def drag_mouse(p, path):
    cs = centers(p)
    x, y = cs[path[0]]
    p.mouse.move(x, y); p.mouse.down()
    for i in path[1:]:
        p.mouse.move(*cs[i], steps=6)
    p.mouse.up()
    p.wait_for_timeout(80)

def drag_touch(p, cdp, path):
    cs = centers(p)
    def ev(t, pts): cdp.send("Input.dispatchTouchEvent", {"type": t, "touchPoints": pts})
    x, y = cs[path[0]]
    ev("touchStart", [{"x": x, "y": y, "id": 1}])
    for i in path[1:]:
        nx, ny = cs[i]
        for s in range(1, 6):
            ev("touchMove", [{"x": x + (nx - x) * s / 5, "y": y + (ny - y) * s / 5, "id": 1}])
        x, y = nx, ny
    ev("touchEnd", [])
    p.wait_for_timeout(80)

def toasts(p): return p.evaluate("Array.from(document.querySelectorAll('.toast')).map(t=>t.textContent)")
def st(p): return p.evaluate("VW.getState()")

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # ---- 1. Today ----
        c, p = open_page(b, la(2026, 9, 30, 12, 40))
        info = p.evaluate("({n:VW.puzzle, tiles:document.querySelectorAll('#grid .gtile').length, slots:document.querySelectorAll('#slots .slot').length, help:!document.getElementById('modal-help').hidden, count:VW.count})")
        pd = p.evaluate("VW.puzzleData(VW.puzzle)")
        print("Today:", info, f"{pd['rows']}x{pd['cols']}")
        check(info["n"] == 1 and pd["rows"] == 5, "today (Wed Sep 30 2026) is puzzle #1 (5x5)")
        check(info["tiles"] == pd["rows"] * pd["cols"] and info["slots"] == len(pd["words"]), "grid and word slots rendered")
        check(info["help"], "how-to-play shown on first visit")
        check(info["count"] >= 150, f"{info['count']} puzzles bundled")
        c.close()
        c, p = open_page(b, la(2026, 9, 29), url=(ROOT / "index.html").as_uri())
        check(p.evaluate("VW.puzzle") == 1 and p.evaluate("document.querySelectorAll('#grid .gtile').length") == 25, "Tue Sep 29 = #1 (5x5); works via file://")
        c.close()
        c, p = open_page(b, la(2026, 10, 1, 9, 0))
        check(p.evaluate("VW.puzzle") == 2 and p.evaluate("document.querySelectorAll('#grid .gtile').length") == 36, "Thu Oct 1 = #2 (6x6)")
        c.close()
        c, p = open_page(b, la(2026, 9, 28, 12, 0))
        check(p.evaluate("VW.puzzle") == 1, "dates before launch fall back to #1")
        c.close()

        # ---- 2. Schedule, next 3+ weeks ----
        c = b.new_context(); p = c.new_page()
        rows = []
        for i in range(0, 28):
            d = dt.date(2026, 9, 29) + dt.timedelta(days=i)
            p.clock.set_fixed_time(la(d.year, d.month, d.day, 0, 1)); p.goto(URL); p.wait_for_function("window.VW")
            rows.append((d, p.evaluate("VW.puzzle"), p.evaluate("(()=>{const q=VW.puzzleData(VW.puzzle);return q.rows+'x'+q.cols})()")))
        ok = True; expected = 0
        for d, n, size in rows:
            if d.weekday() in (1, 3): expected += 1
            if n != expected: ok = False
            want = "5x5" if n % 2 == 1 else "6x6"  # odd = Tuesday puzzle
            if size != want: ok = False
        check(ok, "Tue/Thu advance, other days keep latest; Tue 5x5 / Thu 6x6 (28 days checked)")
        p.clock.set_fixed_time(la(2026, 9, 30, 23, 59)); p.goto(URL); p.wait_for_function("window.VW"); a = p.evaluate("VW.puzzle")
        p.clock.set_fixed_time(la(2026, 10, 1, 0, 0)); p.goto(URL); p.wait_for_function("window.VW"); bb = p.evaluate("VW.puzzle")
        check(a == 1 and bb == 2, "rollover at midnight Pacific (Wed 23:59 -> #1, Thu 00:00 -> #2)")
        p.clock.set_fixed_time(la(2026, 11, 3, 0, 0)); p.goto(URL); p.wait_for_function("window.VW")
        check(p.evaluate("VW.puzzle") == 11, "Tue Nov 3 2026 00:00 PT (after DST ends) is #11")
        p.clock.set_fixed_time(la(2026, 11, 2, 23, 59)); p.goto(URL); p.wait_for_function("window.VW")
        check(p.evaluate("VW.puzzle") == 10, "Mon Nov 2 2026 23:59 PT still #10")
        sched = p.evaluate("Array.from({length:8},(_,i)=>VW.ymdForDayIndex(VW.dayIndexForPuzzle(i+1)))")
        check([dt.date.fromisoformat(x).weekday() for x in sched] == [1, 3] * 4 and sched[0] == "2026-09-29", "puzzle dates fall on Tue/Thu only, starting Sep 29")
        # countdown text on #1 points to #2 on Thu Oct 1
        p.clock.set_fixed_time(la(2026, 9, 30, 13, 0)); p.goto(URL); p.wait_for_function("window.VW"); p.wait_for_timeout(400)
        cdi = p.evaluate("document.getElementById('countdown-inline').textContent")
        print("Countdown text:", cdi)
        check(cdi.startswith("Next puzzle (#2, Thu, Oct 1) in 11:00:0"), "countdown targets #2 at Thu Oct 1 00:00 PT")
        print("\nSchedule (next 3 weeks):")
        for d, n, size in rows[1:22]:
            print(f"  {d.strftime('%a %b %d %Y')}: #{n} ({size})")
        c.close()

        # ---- 3. Gameplay on future puzzle #39 (Tue Feb 9 2027), 360x640 phone ----
        mob = dict(viewport={"width": 360, "height": 640}, device_scale_factor=2, is_mobile=True, has_touch=True,
                   permissions=["clipboard-read", "clipboard-write"])
        c, p = open_page(b, la(2027, 2, 9, 9, 0), install=True, **mob)
        cdp = c.new_cdp_session(p)
        p.click("#modal-help [data-close].btn")
        p.wait_for_timeout(300)
        P = p.evaluate("VW.puzzleData(VW.puzzle)")
        R, C = P["rows"], P["cols"]
        W = P["words"]
        check(p.evaluate("VW.puzzle") == 39, "Tue Feb 9 2027 is puzzle #39")
        fit = p.evaluate("""(()=>{const g=document.getElementById('grid').getBoundingClientRect();const c=document.querySelector('.controls').getBoundingClientRect();
            return {sh:document.documentElement.scrollHeight, sw:document.documentElement.scrollWidth, gl:g.left, gr:g.right, cb:c.bottom, tile:document.querySelector('.gtile').offsetWidth}})()""")
        print("360x640 fit:", fit)
        check(fit["sh"] <= 640 and fit["sw"] <= 360 and fit["gl"] >= 0 and fit["gr"] <= 360 and fit["cb"] <= 640 and fit["tile"] >= 40, "5x5 puzzle fits a 360x640 phone without scrolling (tiles >= 40px)")
        p.screenshot(path=str(ROOT / "screenshot-start.png"))

        # incorrect trace: 3 adjacent open tiles that aren't a hidden word
        grid = P["grid"]
        def nb(i):
            r, cc = divmod(i, C)
            out = []
            if r > 0: out.append(i - C)
            if r < R - 1: out.append(i + C)
            if cc > 0: out.append(i - 1)
            if cc < C - 1: out.append(i + 1)
            return [j for j in out if grid[j] != "#"]
        bad = None
        for s0 in range(R * C):
            if grid[s0] == "#": continue
            for s1 in nb(s0):
                for s2 in nb(s1):
                    if s2 != s0:
                        bad = [s0, s1, s2]; break
                if bad: break
            if bad: break
        drag_mouse(p, bad)
        p.wait_for_timeout(60)
        rej = p.evaluate("({bad:document.querySelectorAll('.gtile.bad').length, shake:document.getElementById('grid').classList.contains('shake'), sel:document.querySelectorAll('.gtile.sel').length})")
        check(st(p)["found"] == [] and rej["bad"] == 3 and rej["shake"] and "Not one of the hidden words" in toasts(p), "incorrect trace rejected: flashes red, shakes, toast, nothing found")
        p.wait_for_timeout(700)
        check(p.evaluate("document.querySelectorAll('.gtile.bad,.gtile.sel').length") == 0, "rejected trace clears")
        # diagonal move ignored
        r0 = next(i for i in range(R * C) if grid[i] != "#" and i % C < C - 1 and i // C < R - 1 and grid[i + C + 1] != "#")
        cs = centers(p)
        p.mouse.move(*cs[r0]); p.mouse.down(); p.mouse.move(*cs[r0 + C + 1], steps=8)
        diag = p.evaluate("document.querySelectorAll('.gtile.sel').length")
        p.mouse.up(); p.wait_for_timeout(700)
        check(diag == 1, "diagonal drag does not extend the trace")
        # reverse direction of a real word is rejected
        drag_mouse(p, W[0]["path"][::-1])
        check(st(p)["found"] == [], "tracing a hidden word backwards is rejected")
        p.wait_for_timeout(700)

        # solve word 0 with the mouse, word 1 with touch (CDP touch events)
        drag_mouse(p, W[0]["path"])
        s = st(p)
        check(s["found"] == [0], f"mouse drag solves {len(W[0]['w'])}-letter word")
        drag_touch(p, cdp, W[1]["path"])
        s = st(p)
        slot_ok = p.evaluate("Array.from(document.querySelectorAll('#slots .slot')[1].children).map(x=>x.textContent).join('')") == W[1]["w"]
        check(s["found"] == [0, 1] and slot_ok, "touch drag solves a word and fills its slot")
        foundtiles = p.evaluate("document.querySelectorAll('.gtile.found').length")
        check(foundtiles == len(W[0]["path"]) + len(W[1]["path"]), "found tiles stay colored")
        # found tiles can't be reused
        drag_mouse(p, W[0]["path"])
        check(st(p)["found"] == [0, 1], "solved tiles cannot be traced again")
        p.wait_for_timeout(200)
        # backtracking during a drag
        cs = centers(p); w2 = W[2]["path"]
        p.mouse.move(*cs[w2[0]]); p.mouse.down()
        for i in w2[1:3]: p.mouse.move(*cs[i], steps=5)
        p.mouse.move(*cs[w2[1]], steps=5)
        back = p.evaluate("document.querySelectorAll('.gtile.sel').length")
        for i in w2[2:]: p.mouse.move(*cs[i], steps=5)
        p.mouse.up(); p.wait_for_timeout(80)
        check(back == 2 and 2 in st(p)["found"], "dragging back over the previous tile un-selects it; word still solvable")
        # undo / reset
        p.click("#btn-undo"); check(st(p)["found"] == [0, 1], "Undo removes the last found word")
        p.click("#btn-reset"); check(st(p)["found"] == [] and p.evaluate("document.querySelectorAll('.gtile.found').length") == 0, "Reset clears all found words")
        check(p.evaluate("document.getElementById('btn-undo').disabled && document.getElementById('btn-reset').disabled"), "Undo/Reset disabled on an empty board")
        drag_mouse(p, W[0]["path"]); drag_touch(p, cdp, W[1]["path"])
        p.clock.run_for(38000)
        p.evaluate("document.querySelectorAll('.toast').forEach(t=>t.remove())")
        p.screenshot(path=str(ROOT / "screenshot-midway.png"))

        # timer pauses while a dialog is open
        e0 = st(p)["elapsed"]; p.click("#btn-help"); p.clock.run_for(30000); e1 = st(p)["elapsed"]
        p.click("#modal-help [data-close].btn"); p.wait_for_timeout(100)
        check(e1 - e0 < 3000, "timer pauses while the help dialog is open")
        # hint
        tgt = 2
        p.click("#btn-hint"); p.wait_for_timeout(50)
        s = st(p)
        h1 = p.evaluate(f"document.querySelectorAll('.gtile')[{W[tgt]['path'][0]}].classList.contains('hint')")
        sl1 = p.evaluate(f"document.querySelectorAll('#slots .slot')[{tgt}].children[0].textContent")
        check(s["hints"] == 1 and s["reveal"][tgt] == 1 and h1 and sl1 == W[tgt]["w"][0], "Hint highlights the start tile and reveals the first letter")
        p.click("#btn-hint"); s = st(p)
        h2 = p.evaluate(f"document.querySelectorAll('.gtile')[{W[tgt]['path'][1]}].classList.contains('hint')")
        check(s["hints"] == 2 and s["reveal"][tgt] == 2 and h2, "second Hint reveals the next letter of the same word")
        p.clock.run_for(64000)
        for j in range(2, len(W)):
            (drag_mouse if j % 2 == 0 else (lambda pg, path: drag_touch(pg, cdp, path)))(p, W[j]["path"])
        s = st(p)
        check(s["status"] == "won" and sorted(s["found"]) == list(range(len(W))), "all words found -> solved")
        p.clock.run_for(2500)
        res = p.evaluate("""({open:!document.getElementById('modal-stats').hidden, cards:document.querySelectorAll('.wcard').length,
            defs:Array.from(document.querySelectorAll('.wcard .wd')).map(x=>x.textContent), theme:document.getElementById('res-theme').textContent,
            time:document.getElementById('res-time').textContent, hints:document.getElementById('res-hints').textContent, cd:document.getElementById('countdown').textContent,
            solved:document.getElementById('st-played').textContent, streak:document.getElementById('st-streak').textContent})""")
        print("Results:", {k: v for k, v in res.items() if k != "defs"})
        check(res["open"] and res["cards"] == len(W) and all(len(d) > 15 for d in res["defs"]) and res["theme"].startswith("Theme: "), "results screen: theme + every word with its definition")
        check(res["hints"] == "2" and res["solved"] == "1" and res["streak"] == "1" and res["cd"] != "--:--:--", "results show hints, stats, streak, countdown")
        share = p.evaluate("VW.shareText()")
        lines = share.split("\n")
        emo = "".join("🟨" if j == tgt else "🟩" for j in range(len(W)))
        check(lines[0] == "VectorWend #39 🦟" and lines[1].startswith("Solved in ") and lines[1].endswith(" | 2 hints") and lines[2] == emo and lines[3] == URL and len(lines) == 4,
              "share text format (header, time | hints, one emoji per word, URL without query/hash)")
        check(not any(w["w"] in share for w in W), "share text is spoiler-free")
        elapsed = st(p)["elapsed"]
        check(102000 <= elapsed <= 135000 and res["time"] == lines[1].split()[2], f"timer counted play time ({elapsed/1000:.1f}s incl. ~10s of real test time)")
        # share button + LinkedIn
        p.evaluate("navigator.share = undefined")
        p.click("#btn-share"); p.wait_for_timeout(300)
        clip = p.evaluate("navigator.clipboard.readText()")
        check(clip == share, "Share button copies result to clipboard")
        c.route("https://www.linkedin.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body="stub"))
        with c.expect_page() as newp:
            p.click("#btn-linkedin")
        newp.value.wait_for_load_state()
        li = newp.value.url
        q = urllib.parse.parse_qs(urllib.parse.urlparse(li).query)
        check(li.startswith("https://www.linkedin.com/feed/?shareActive=true&text=") and q.get("text", [""])[0] == share, "Post to LinkedIn opens share URL with encoded result (+ copies)")
        newp.value.close()
        p.evaluate("document.querySelectorAll('.toast').forEach(t=>t.remove())")
        p.evaluate("document.querySelector('#modal-stats .modal-card').scrollTop=0")
        p.wait_for_timeout(200)
        p.screenshot(path=str(ROOT / "screenshot-results.png"))
        p.reload(); p.wait_for_function("window.VW"); p.clock.run_for(800)
        per = p.evaluate("({s:VW.getState().status, f:document.querySelectorAll('.gtile.found').length, solved:VW.getStats().played, open:!document.getElementById('modal-stats').hidden})")
        check(per["s"] == "won" and per["f"] == sum(len(w['path']) for w in W) and per["solved"] == 1 and per["open"], "finished game + stats persist across reload (no double count)")
        c.close()

        # ---- 4. 6x6 (#42, Thu Feb 18 2027) fits 360x640; auto-solve via hints ----
        c, p = open_page(b, la(2027, 2, 18, 9, 0), **mob)
        close_modals(p)
        fit = p.evaluate("""(()=>{const g=document.getElementById('grid').getBoundingClientRect();const c=document.querySelector('.controls').getBoundingClientRect();
            return {n:VW.puzzle, sh:document.documentElement.scrollHeight, gr:g.right, cb:c.bottom, tile:document.querySelector('.gtile').offsetWidth}})()""")
        print("6x6 fit:", fit)
        check(fit["n"] == 42 and fit["sh"] <= 640 and fit["gr"] <= 360 and fit["cb"] <= 640 and fit["tile"] >= 38, "6x6 puzzle fits a 360x640 phone")
        P2 = p.evaluate("VW.puzzleData(VW.puzzle)")
        for _ in range(len(P2["words"][0]["w"])): p.click("#btn-hint")
        check(st(p)["found"] == [0], "revealing every letter via Hint completes that word")
        c.close()

        # desktop layout sanity
        c, p = open_page(b, la(2026, 12, 30, 9, 0), viewport={"width": 1280, "height": 800})
        close_modals(p)
        dsk = p.evaluate("({sh:document.documentElement.scrollHeight, tile:document.querySelector('.gtile').offsetWidth})")
        check(dsk["sh"] <= 800 and dsk["tile"] >= 56, f"desktop layout fits (tile {dsk['tile']}px)")
        c.close()
        b.close()
    check(not errors, "no page errors: %s" % errors[:3])
finally:
    srv.terminate()

print("\n%d failure(s)" % len(fails))
sys.exit(1 if fails else 0)
