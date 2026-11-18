import re
from playwright.sync_api import sync_playwright, expect
BASE = "http://localhost:5173"
results, errs = [], []
def step(n, f):
    try: f(); results.append((n, "PASS", ""))
    except Exception as e: results.append((n, "FAIL", str(e).splitlines()[0][:220])); print("FAIL", n, str(e)[:400])

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(path="yt_stub.js")
    ctx.route("https://www.youtube.com/iframe_api", lambda r: r.fulfill(status=200, content_type="text/javascript", body="window.onYouTubeIframeAPIReady&&window.onYouTubeIframeAPIReady();"))
    page = ctx.new_page()
    page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))

    page.goto(BASE + "/login"); page.get_by_label("Email").fill("friend@rove.test"); page.get_by_label("Password").fill("password123")
    page.get_by_role("button", name=re.compile("Log in")).click(); page.wait_for_url("**/start")

    def build():
        page.get_by_role("button", name="House party").click(); page.get_by_role("button", name=re.compile("Next")).click()
        expect(page.get_by_role("button", name=re.compile("^Hindi"))).to_contain_text("Full catalogue ready")
        page.get_by_role("button", name=re.compile("^Hindi")).click(); page.get_by_role("button", name=re.compile("Next")).click()
        page.get_by_role("button", name=re.compile("Next")).click()
        page.get_by_role("button", name=re.compile("Peak")).click(); page.get_by_role("button", name=re.compile("Next")).click()
        page.get_by_role("button", name=re.compile("^10-20")).click(); page.get_by_role("button", name=re.compile("Build my set")).click()
        page.wait_for_url("**/review", timeout=15000)
        expect(page.locator("li.row")).to_have_count(6, timeout=8000)
        titles = [t.upper() for t in page.locator("li.row .t").all_inner_texts()]
        assert len(titles) == 6, titles                       # 8 returned, 2 filtered (not embeddable, too short)
        assert "NOT EMBEDDABLE" not in titles and "TOO SHORT" not in titles
    step("YouTube search -> set (non-embeddable + shorts filtered; open catalogue label)", build)

    def live_starts():
        page.get_by_role("button", name=re.compile("Approve")).click(); page.wait_for_url("**/live")
        expect(page.locator(".yt-tile")).to_be_visible(timeout=10000)
        box = page.locator(".yt-tile").bounding_box(); assert box["width"] >= 200 and box["height"] >= 200, box
        page.wait_for_function("window.__yt.loads.length >= 1", timeout=8000)
    step("Live: official-player tile visible (>=200x200) and a video loads", live_starts)

    def state_for_playing():
        # Wait for a normal track: "Blocked" is skipped instantly and "Dies Midway" fails by design 2s in.
        for _ in range(30):
            page.wait_for_timeout(600)
            if page.locator(".live .song").inner_text().upper() not in ("BLOCKED VIDEO", "DIES MIDWAY"):
                page.wait_for_timeout(600); return
    def time_of(): return page.locator(".timer-pill").inner_text().split("/")[0].strip().split()[-1]
    def play_pause():
        state_for_playing()
        t0 = time_of(); page.wait_for_timeout(2200); assert time_of() != t0, "YouTube time not advancing"
        expect(page.locator(".progress-track")).to_be_visible()
        page.get_by_role("button", name="Pause").click(); expect(page.locator(".paused-word")).to_be_visible()
        tp = time_of(); page.wait_for_timeout(1500); assert time_of() == tp
        page.keyboard.press("Space"); page.wait_for_timeout(1500); assert time_of() != tp
    step("play, progress bar, pause overlay, resume (via player API)", play_pause)

    def seek():
        box = page.locator(".wave").bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] / 2)
        page.wait_for_function("window.__yt.lastSeek > 90", timeout=3000)
    step("click progress bar seeks the YouTube player", seek)

    def run_through():
        for _ in range(14):
            if "/done" in page.url: break
            title = page.locator(".live .song").inner_text().upper() if page.locator(".live .song").count() else ""
            if title == "DIES MIDWAY":
                page.wait_for_function("t => document.querySelector('.live .song')?.innerText.toUpperCase() !== t || location.pathname === '/done'", arg=title, timeout=9000)
            elif title == "BLOCKED VIDEO":
                page.wait_for_timeout(1200)
            else:
                page.wait_for_timeout(500); page.get_by_role("button", name="Skip", exact=True).click(); page.wait_for_timeout(900)
        page.wait_for_url("**/done", timeout=15000)
    step("blocked video + mid-play failure are skipped; set continues to completion", run_through)

    def summary():
        rows = [(x.locator(".dt").inner_text().upper(), "skipped" in (x.get_attribute("class") or "")) for x in page.locator(".done-list li").all()]
        print("DONE LIST:", rows)
        assert len(rows) == 6, f"rows={len(rows)}"
        sk = {t for t, k in rows if k}
        assert "BLOCKED VIDEO" in sk, f"skipped={sk}"
        assert "DIES MIDWAY" in sk, f"skipped={sk}"
    step("completion summary marks blocked + failed tracks as skipped", summary)
    b.close()

w = max(len(r[0]) for r in results)
for n, s, m in results: print(f"{s:5} {n:<{w}} {m}")
print("console errors:", len(errs))
for e in errs[:8]: print("  ", e[:180])
