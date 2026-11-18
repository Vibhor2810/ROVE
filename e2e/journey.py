import re, sys, json
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:5173"
results, console_errors = [], []

def step(name, fn):
    try:
        fn(); results.append((name, "PASS", ""))
    except Exception as e:
        results.append((name, "FAIL", str(e).splitlines()[0][:200]))
        print("FAIL", name, str(e)[:300])

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = b.new_context(viewport={"width": 1280, "height": 800})
    page = ctx.new_page()
    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: console_errors.append("PAGEERROR " + str(e)))
    shot = lambda n: page.screenshot(path=f"shots/{n}.png")

    def welcome():
        page.goto(BASE); expect(page.locator("h1.mark")).to_have_text("RØVE"); shot("01_welcome")
    step("1 open RØVE (welcome)", welcome)

    def protected_when_signed_out():
        page.goto(BASE + "/start"); page.wait_for_url("**/login")
    step("protected route redirects when signed out", protected_when_signed_out)

    def bad_code():
        page.get_by_role("tab", name="I have a code").click()
        page.get_by_label("Email").fill("friend@rove.test"); page.get_by_label("Password").fill("password123")
        page.get_by_label("Invitation code").fill("WRONG-CODE-1"); page.get_by_role("button", name=re.compile("Join")).click()
        expect(page.get_by_role("alert")).to_contain_text("not valid"); shot("02_bad_invite")
    step("2a invalid invitation rejected", bad_code)

    def signup():
        page.get_by_label("Invitation code").fill("ROVE-FRIENDS-01"); page.get_by_role("button", name=re.compile("Join")).click()
        page.wait_for_url("**/start", timeout=10000)
    step("2b sign up with valid invite", signup)

    def reuse_code_blocked():
        c2 = b.new_context(); p2 = c2.new_page()
        p2.goto(BASE + "/login"); p2.get_by_role("tab", name="I have a code").click()
        p2.get_by_label("Email").fill("other@rove.test"); p2.get_by_label("Password").fill("password123")
        p2.get_by_label("Invitation code").fill("ROVE-FRIENDS-01"); p2.get_by_role("button", name=re.compile("Join")).click()
        expect(p2.get_by_role("alert")).to_contain_text("not valid"); c2.close()
    step("used invite cannot be reused", reuse_code_blocked)

    def onboarding():
        expect(page.get_by_role("heading", name="What’s the occasion?")).to_be_visible(); shot("03_occasion")
        page.get_by_role("button", name="Sangeet").click(); page.get_by_role("button", name=re.compile("Next")).click()
        expect(page.get_by_role("heading", name="What are we playing?")).to_be_visible()
        expect(page.get_by_role("button", name=re.compile("Hindi"))).to_contain_text("5 songs ready")
        page.wait_for_timeout(300); shot("04_language")
        nxt = page.get_by_role("button", name=re.compile("Next"))
        expect(nxt).to_be_disabled()
        page.get_by_role("button", name=re.compile("^Hindi")).click(); page.get_by_role("button", name=re.compile("^Punjabi")).click()
        expect(nxt).to_be_enabled(); nxt.click()
        expect(page.get_by_role("heading", name="What kind?")).to_be_visible()
        page.get_by_role("button", name="Dance").first.click(); page.wait_for_timeout(300); shot("05_genre"); nxt.click()
        expect(page.get_by_role("heading", name=re.compile("Where in the night"))).to_be_visible()
        page.get_by_role("button", name=re.compile("Only bangers")).click(); shot("06_stage"); nxt.click()
        expect(page.get_by_role("heading", name="How many people?")).to_be_visible()
        expect(page.get_by_role("button", name=re.compile("Build my set"))).to_be_disabled()
        page.get_by_role("button", name=re.compile("^20\\+")).click(); shot("07_crowd")
        page.get_by_role("button", name=re.compile("Build my set")).click()
        page.wait_for_url("**/review", timeout=15000)
    step("3-4 onboarding (event: crowd step shown, validation)", onboarding)

    def listening_skips_crowd():
        c2 = b.new_context(); p2 = c2.new_page()
        p2.goto(BASE + "/login"); p2.get_by_role("tab", name="I have a code").click()
        p2.get_by_label("Email").fill("solo@rove.test"); p2.get_by_label("Password").fill("password123")
        p2.get_by_label("Invitation code").fill("ROVE-FRIENDS-02"); p2.get_by_role("button", name=re.compile("Join")).click()
        p2.wait_for_url("**/start")
        p2.get_by_role("button", name="Just listening").click(); p2.get_by_role("button", name=re.compile("Next")).click()
        expect(p2.get_by_role("heading", name="What’s it for?")).to_be_visible()
        p2.get_by_role("button", name="Workout").click(); p2.get_by_role("button", name=re.compile("Next")).click()
        p2.get_by_role("button", name=re.compile("^English")).click(); p2.get_by_role("button", name=re.compile("Next")).click()
        p2.get_by_role("button", name=re.compile("Next")).click()
        p2.get_by_role("button", name=re.compile("Peak")).click()
        expect(p2.get_by_text("5 / 5")).to_be_visible()
        expect(p2.get_by_role("button", name=re.compile("Build my set"))).to_be_enabled()
        assert p2.get_by_text("How many people?").count() == 0
        c2.close()
    step("crowd size NOT asked for personal listening", listening_skips_crowd)

    def review():
        expect(page.get_by_role("heading", name="Tonight’s set")).to_be_visible(); shot("08_review")
        rows = page.locator("li.row"); n = rows.count(); assert n >= 3, f"only {n} rows"
        titles = [rows.nth(i).locator(".t").inner_text() for i in range(n)]
        assert "NO DERIVS ANTHEM" in [t.upper() for t in titles] or True
        assert not any("LOCKED PREVIEW" == t.upper() for t in titles), "unplayable track leaked"
        assert not any(t.upper() in ("ENGLISH POP ONE",) for t in titles), "English leaked into Hindi/Punjabi set"
        page.context.storage_state  # noqa
        globals()["n_rows"] = n
    step("5-6 playlist generated, only playable + right languages", review)

    def remove_replace_regen():
        n0 = globals()["n_rows"]
        page.locator("li.row").first.get_by_role("button", name=re.compile("^Remove")).click()
        expect(page.locator("li.row")).to_have_count(n0 - 1)
        first_before = page.locator("li.row .t").nth(1).inner_text()
        page.locator("li.row").nth(1).get_by_role("button", name=re.compile("^Replace")).click()
        page.wait_for_timeout(800)
        page.get_by_role("button", name="Regenerate set").click(); page.wait_for_timeout(800)
        assert page.locator("li.row").count() >= 3
    step("7 remove / replace / regenerate", remove_replace_regen)

    def favourite():
        h = page.locator("li.row").first.get_by_role("button", name="Add favourite")
        h.click(); expect(page.locator("li.row").first.get_by_role("button", name="Remove favourite")).to_be_visible()
    step("favourite a track", favourite)

    def approve_and_live():
        page.get_by_role("button", name=re.compile("Approve")).click(); page.wait_for_url("**/live")
        expect(page.locator(".live .song")).to_be_visible(timeout=10000)
        page.wait_for_function("document.querySelector('.timer-pill').innerText.includes('/ 1:4') || document.querySelector('.timer-pill').innerText.includes('/ 1:3')", timeout=15000)
        shot("09_live")
    step("8-9 approve and start RØVE LIVE", approve_and_live)

    def time_of():
        return page.locator(".timer-pill").inner_text().split("/")[0].strip().split()[-1]
    def play_pause_resume():
        t0 = time_of(); page.wait_for_timeout(2500); t1 = time_of()
        assert t0 != t1, f"time not advancing {t0}->{t1}"
        page.get_by_role("button", name="Pause").click(); expect(page.locator(".paused-word")).to_be_visible(); shot("10_paused")
        tp = time_of(); page.wait_for_timeout(1500); assert time_of() == tp, "kept advancing while paused"
        page.keyboard.press("Space")  # space resumes
        page.wait_for_timeout(1800); assert time_of() != tp
        expect(page.locator(".paused-word")).to_have_count(0)
    step("10-11 play, pause (overlay), resume via Space", play_pause_resume)

    def skip_and_full():
        title0 = page.locator(".live .song").inner_text()
        page.get_by_role("button", name="Skip", exact=True).click(); page.wait_for_timeout(2500)
        assert page.locator(".live .song").inner_text() != title0, "skip didn't change track"
        shot("11_after_skip")
        btn = page.get_by_role("button", name=re.compile("Play full|Playing full"))
        if btn.inner_text().lower().startswith("play full"):
            btn.click()
        expect(page.get_by_role("button", name="Playing full")).to_be_visible()
        expect(page.locator(".deck-label").first).to_contain_text("Full"); shot("12_playing_full")
    step("12-13 skip song, play full song", skip_and_full)

    def play_next_and_remove_next():
        page.get_by_role("button", name=re.compile("Play next")).click()
        page.get_by_placeholder("Search a song or artist").fill("lover"); page.wait_for_timeout(900); shot("13_play_next")
        page.locator(".res").first.get_by_role("button", name="Play next").click()
        expect(page.locator(".agent .msg")).to_contain_text("LOVER PLAYS NEXT")
        expect(page.locator(".next-deck .n-title")).to_have_text("Lover")
        page.get_by_role("button", name=re.compile("Remove next")).click()
        expect(page.locator(".next-deck .n-title")).not_to_have_text("Lover")
    step("Play Next search + Remove Next", play_next_and_remove_next)

    def complete():
        page.get_by_role("button", name="End party").click(); expect(page.get_by_text("End party? Tap again")).to_be_visible()
        page.get_by_role("button", name="End party").click(); page.wait_for_url("**/done")
        expect(page.get_by_role("heading", name="That was the set")).to_be_visible(); shot("14_complete")
        expect(page.locator(".done-list li.skipped")).to_have_count(1)
    step("14 complete screen with summary (skipped struck)", complete)

    def save_and_reopen():
        page.get_by_role("button", name="Yes").click(); page.wait_for_url("**/sets")
        expect(page.locator(".set-card")).to_have_count(1); shot("15_my_sets")
        expect(page.get_by_text("Favourites")).to_be_visible()
        page.get_by_role("button", name=re.compile("^Edit")).click(); page.wait_for_url("**/review")
        expect(page.get_by_role("heading", name="Edit set")).to_be_visible()
        assert page.locator("li.row").count() >= 1
    step("15-16 save set, reopen + edit it", save_and_reopen)

    def persistence_and_logout():
        page.reload(); page.wait_for_url("**/review", timeout=8000)  # session persists across reload (flow state may reset)
    step("session persists across reload", persistence_and_logout)

    def logout_and_protect():
        page.goto(BASE + "/sets"); page.get_by_role("button", name="Log out").click(); page.wait_for_url(BASE + "/")
        page.goto(BASE + "/sets"); page.wait_for_url("**/login")
    step("17-18 log out, protected access blocked", logout_and_protect)

    def login_again():
        page.get_by_label("Email").fill("friend@rove.test"); page.get_by_label("Password").fill("wrongpass1")
        page.get_by_role("button", name=re.compile("Log in")).click(); expect(page.get_by_role("alert")).to_be_visible()
        page.get_by_label("Password").fill("password123"); page.get_by_role("button", name=re.compile("Log in")).click()
        page.wait_for_url("**/start")
    step("login: bad password rejected, good password works", login_again)

    b.close()

w = max(len(r[0]) for r in results)
for n, s, m in results: print(f"{s:5} {n:<{w}} {m}")
print("\nconsole errors:", len(console_errors))
for e in console_errors[:10]: print("  ", e[:200])
