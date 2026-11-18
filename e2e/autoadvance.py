import re
from playwright.sync_api import sync_playwright, expect
BASE="http://localhost:5173"
with sync_playwright() as p:
    b=p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"]); page=b.new_page(viewport={"width":1280,"height":800})
    page.goto(BASE+"/login"); page.get_by_label("Email").fill("friend@rove.test"); page.get_by_label("Password").fill("password123")
    page.get_by_role("button", name=re.compile("Log in")).click(); page.wait_for_url("**/start")
    page.get_by_role("button", name="House party").click(); page.get_by_role("button", name=re.compile("Next")).click()
    page.get_by_role("button", name=re.compile("^Hindi")).click(); page.get_by_role("button", name=re.compile("Next")).click()
    page.get_by_role("button", name=re.compile("Next")).click()
    page.get_by_role("button", name=re.compile("Peak")).click(); page.get_by_role("button", name=re.compile("Next")).click()
    page.get_by_role("button", name=re.compile("^10-20")).click(); page.get_by_role("button", name=re.compile("Build my set")).click()
    page.wait_for_url("**/review"); page.get_by_role("button", name=re.compile("Approve")).click(); page.wait_for_url("**/live")
    expect(page.locator(".live .song")).to_be_visible(timeout=10000)
    # find a segment-capable track (ND track plays full, has no OUT marker)
    for _ in range(6):
        page.wait_for_timeout(5500)  # let analysis land
        if "OUT" in page.locator(".wave-marks").inner_text().upper(): break
        page.get_by_role("button", name="Skip", exact=True).click()
    marks=page.locator(".wave-marks").inner_text().replace("\n"," "); print("marks:", marks)
    assert "OUT" in marks.upper(), "no segment track found"
    title=page.locator(".live .song").inner_text()
    box=page.locator(".wave").bounding_box()
    page.mouse.click(box["x"]+box["width"]*0.85, box["y"]+box["height"]/2)   # set IN near 85s -> OUT=100s
    page.wait_for_timeout(600); print("after pick:", page.locator(".wave-marks").inner_text().replace("\n"," "), "|", page.locator(".agent .msg").inner_text())
    page.wait_for_function("t => document.querySelector('.live .song').innerText !== t", arg=title, timeout=30000)
    print("auto-advanced:", title, "->", page.locator(".live .song").inner_text(), "|", page.locator(".agent .msg").inner_text())
    b.close()
