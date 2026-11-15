"""Record the demo video and README screenshots by driving the real app in Chrome.

Development tool only. Start the app on a fresh database, then run:

    LEARNTRACK_DB=/tmp/demo.sqlite PORT=5055 python app.py &
    python scripts/record_demo.py http://127.0.0.1:5055

Outputs: docs/demo/learntrack-demo.mp4, docs/screenshots/*.png and
docs/sample-data/ (real exports produced during the run).
The caption bar and the cursor dot are overlays added by this script for the
recording; they are not part of the app.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5055"
ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
DEMO = ROOT / "docs" / "demo"
SAMPLES = ROOT / "docs" / "sample-data"
LA = "/course/learning-analytics/lesson/"
WEB = "/course/web-fundamentals/lesson/"

OVERLAY = """
(() => {
  const add = () => {
    if (document.getElementById('demo-caption')) return;
    const bar = document.createElement('div');
    bar.id = 'demo-caption';
    bar.setAttribute('data-no-track', '');
    bar.style.cssText = 'position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:9999;max-width:900px;' +
      'background:rgba(20,28,34,.94);color:#fff;font:600 19px/1.35 system-ui,sans-serif;padding:12px 22px;' +
      'border-radius:12px;border-left:5px solid #e8a94c;pointer-events:none;box-shadow:0 6px 24px rgba(0,0,0,.3)';
    bar.textContent = sessionStorage.getItem('demoCaption') || '';
    bar.style.display = bar.textContent ? 'block' : 'none';
    const dot = document.createElement('div');
    dot.id = 'demo-cursor';
    dot.style.cssText = 'position:fixed;z-index:10000;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;' +
      'background:rgba(232,169,76,.55);border:2px solid #b9741f;pointer-events:none;left:-50px;top:-50px;transition:transform .1s';
    const [x, y] = (sessionStorage.getItem('demoCursor') || '-50,-50').split(',');
    dot.style.left = x + 'px'; dot.style.top = y + 'px';
    document.documentElement.append(bar, dot);
    addEventListener('mousemove', e => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px';
      sessionStorage.setItem('demoCursor', e.clientX + ',' + e.clientY); }, true);
    addEventListener('mousedown', () => dot.style.transform = 'scale(.6)', true);
    addEventListener('mouseup', () => dot.style.transform = '', true);
  };
  if (document.documentElement) add();
  document.addEventListener('DOMContentLoaded', add);
})();
"""


class Driver:
    def __init__(self, page, human=True):
        self.page, self.human = page, human

    def pause(self, ms):
        self.page.wait_for_timeout(ms if self.human else min(ms, 250))

    def caption(self, text, hold=2200):
        self.page.evaluate(
            "t => { sessionStorage.setItem('demoCaption', t); const b = document.getElementById('demo-caption');"
            " if (b) { b.textContent = t; b.style.display = t ? 'block' : 'none'; } }", text)
        self.pause(hold)

    def click(self, selector, after=900):
        target = self.page.locator(selector).first
        target.wait_for(state="visible")
        box = target.bounding_box()
        height = self.page.viewport_size["height"]
        if box["y"] < 90 or box["y"] + box["height"] > height - 90:   # keep clear of the sticky header
            target.evaluate("el => el.scrollIntoView({block: 'center'})")
            self.page.wait_for_timeout(700)
            box = target.bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=22 if self.human else 1)
        self.pause(250)
        self.page.mouse.down()
        self.pause(90)
        self.page.mouse.up()
        self.pause(after)

    def type(self, selector, text):
        self.click(selector, after=150)
        self.page.keyboard.type(text, delay=55 if self.human else 0)
        self.pause(250)

    def scroll(self, pixels, step=120):
        for _ in range(abs(pixels) // step):
            self.page.mouse.wheel(0, step if pixels > 0 else -step)
            self.pause(110)
        self.pause(500)

    def goto(self, path):
        self.page.goto(BASE + path)
        self.page.wait_for_load_state()

    def register(self, name, username, password="learn123"):
        self.goto("/register")
        self.type("[name=full_name]", name)
        self.type("[name=email]", f"{username}@example.com")
        self.type("[name=username]", username)
        self.type("[name=password]", password)
        self.click("#register-form button")

    def login(self, username, password):
        self.type("[name=username]", username)
        self.type("[name=password]", password)
        self.click("#login-form button")

    def take_quiz(self, answers):
        self.click("#quiz-start")
        for question, choice in answers:
            self.click(f"input[name={question}][value='{choice}']", after=450)
        self.click("#quiz-submit", after=0)
        self.page.wait_for_timeout(1600)   # result box scrolls into view


def background_learners(browser):
    """Two more learners use the app (not recorded) so class analytics has several people."""
    plans = [
        ("Ravi Kumar", "ravi", [("q1", 0), ("q2", 1), ("q3", 1), ("q4", 3), ("q5", 1)], 9),
        ("Meera Shah", "meera", [("q1", 0), ("q2", 1), ("q3", 2), ("q4", 1), ("q5", 1)], 24),
    ]
    for name, username, answers, watch_seconds in plans:
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        d = Driver(context.new_page(), human=False)
        d.register(name, username)
        d.click("text=Start course")
        d.scroll(1400)
        d.click("details summary")
        d.click(".check .option >> nth=1")
        d.click("#complete-btn")
        d.click("text=Next →")
        d.click("video")
        d.page.wait_for_timeout(watch_seconds * 1000)
        d.click("video")
        if username == "ravi":
            d.click("[data-rewind]")
            d.click("video"); d.page.wait_for_timeout(4000); d.click("video")
            d.click("[data-rewind]")
        else:
            d.click("[data-speed='1.5']")
            d.click(".check .option >> nth=2")
            d.click("#complete-btn")
        d.goto(LA + "la-quiz")
        d.take_quiz(answers)
        if username == "ravi":   # failed first time: review and try again
            d.click("#quiz-retry")
            d.take_quiz([("q1", 0), ("q2", 1), ("q3", 2), ("q4", 1), ("q5", 0)])
        else:
            d.goto(WEB + "how-the-web-works")
            d.click(".check .option >> nth=1")
            d.click("#complete-btn")
            d.goto(WEB + "http-in-60-seconds")
            d.click("video"); d.page.wait_for_timeout(6000); d.click("video")
        d.goto("/activity")
        d.click("text=Log out")
        context.close()


def recorded_walkthrough(browser, video_dir):
    context = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(video_dir),
                                  record_video_size={"width": 1280, "height": 720},
                                  timezone_id="Asia/Kolkata", locale="en-GB")
    context.add_init_script(OVERLAY)
    page = context.new_page()
    d = Driver(page)

    d.goto("/login")
    d.caption("LearnTrack: a learning web app that records every learner action as clickstream data.", 3500)
    d.caption("1. Learners log in. New learners can create an account.")
    d.click("text=Create a learner account")
    d.type("[name=full_name]", "Priya Nair")
    d.type("[name=email]", "priya@example.com")
    d.type("[name=username]", "priya")
    d.type("[name=password]", "learn123")
    d.click("#register-form button")
    d.caption("Dashboard: two courses with progress. The badge (bottom left) counts events tracked on this page.", 3500)
    d.click("text=Start course")

    d.caption("2. Text lesson: reading material with interactive parts.", 2500)
    d.scroll(700)
    d.caption("Scroll depth (25 / 50 / 75 / 100%) is tracked as the learner reads.", 2200)
    d.click("details summary")
    d.caption("Expanding a “Dig deeper” section is recorded.", 1800)
    d.click(".check .option >> nth=0")
    d.caption("Quick check: a wrong answer, then the right one. Both attempts are logged.", 1500)
    d.click(".check .option >> nth=1", after=1800)
    d.scroll(600)
    d.click("#complete-btn")
    d.caption("Marking the lesson complete updates progress.", 1500)
    d.click("text=Next →")

    d.caption("3. Text + video lesson. Every video action is captured with the position in the video.", 3000)
    d.click("video", after=200)
    d.caption("Play …", 5200)
    d.click("video", after=200)
    d.caption("… pause …", 1500)
    d.click("[data-rewind]", after=200)
    d.caption("… skip back 10 s …", 1500)
    d.click("[data-speed='1.5']", after=200)
    d.caption("… change speed to 1.5× …", 1500)
    d.click("video", after=200)
    d.caption("… and resume. Progress milestones (25 / 50 / 75%) and completion are tracked too.", 4500)
    d.click("video")
    d.scroll(900)
    d.click(".check .option >> nth=2", after=1600)
    d.scroll(500)
    d.click("#complete-btn")

    d.goto(LA + "la-quiz")
    d.caption("4. Quiz: attempts are stored and graded on the server.", 2500)
    d.click("#quiz-start")
    d.caption("Each selected answer, including changed answers, is an event.", 800)
    for question, choice in [("q1", 0), ("q2", 1), ("q3", 0), ("q3", 2), ("q4", 1), ("q5", 0)]:
        d.click(f"input[name={question}][value='{choice}']", after=500)
    d.click("#quiz-submit", after=1500)
    d.caption("Score, pass / fail and an explanation for every question.", 3500)
    d.scroll(-700)
    d.pause(1200)

    d.click("text=My activity")
    d.caption("5. My activity: the learner's own clickstream, straight from the database.", 3500)
    d.scroll(500)
    d.caption("Columns follow the Moodle log format: time, event context, component, event name, description, origin, IP.", 3500)
    d.scroll(-500)
    page.select_option("select[name=component]", "Video")
    d.pause(600)
    d.click("#event-filters button[type=submit]")
    d.caption("Filter by component: only the video events.", 2500)
    d.click("details.meta summary", after=600)
    d.caption("Each event also carries JSON metadata: video position, speed, seconds watched.", 3200)
    d.click("#event-filters a")
    d.caption("6. Export: CSV in the Moodle format, CSV with all columns, or JSON.", 1500)
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for label, filename in [("Export CSV (Moodle format)", "clickstream-moodle-format.csv"),
                            ("Export CSV (all columns)", "clickstream-all-columns.csv"),
                            ("Export JSON", "clickstream.json")]:
        with page.expect_download() as download:
            d.click(f"[data-track-label='{label}']", after=500)
        download.value.save_as(str(SAMPLES / filename))
    d.caption("Three files downloaded. The export itself is logged as an event.", 2500)

    d.click("text=Log out")
    d.caption("7. The instructor account sees the whole class.", 1500)
    d.login("instructor", "teach123")
    d.click("text=Class analytics")
    d.caption("Class analytics: totals and charts computed live from the events table.", 3500)
    d.scroll(700)
    d.caption("Per-learner activity, progress and quiz results.", 3000)
    d.click("[data-track-label^='View clickstream of user']", after=1200)
    d.caption("The full log for all users, filterable by learner, event and date, with the same exports.", 3500)
    d.scroll(500)
    d.caption("Stack: Python (Flask) + SQLite + plain JavaScript. 24 automated tests. Code and README are in the repository.", 4500)
    d.caption("", 300)
    video_path = page.video.path()
    context.close()
    return Path(video_path)


def screenshots(browser):
    """Clean screenshots (no overlays) of every main screen, using the data created above."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5,
                                  timezone_id="Asia/Kolkata", locale="en-GB")
    page = context.new_page()
    d = Driver(page, human=False)

    def shot(name, **kwargs):
        page.wait_for_timeout(400)
        page.screenshot(path=str(SHOTS / f"{name}.png"), **kwargs)

    d.goto("/login"); shot("01-login")
    d.goto("/register"); shot("02-register")
    d.goto("/login"); d.login("priya", "learn123"); shot("03-dashboard")
    d.goto("/course/learning-analytics"); shot("04-course")
    d.goto(LA + "ethics-privacy")
    d.click("details summary"); d.click(".check .option >> nth=0"); d.click(".check .option >> nth=1")
    page.evaluate("window.scrollTo(0, 330)"); shot("05-text-lesson")
    d.goto(LA + "clickstream-explained")
    d.click("video"); page.wait_for_timeout(12500); d.click("video"); d.click("[data-speed='1.5']")
    page.mouse.move(640, 420); page.evaluate("window.scrollTo(0, 150)"); shot("06-video-lesson")
    d.goto(LA + "la-quiz")
    d.click("#quiz-start")
    for question, choice in [("q1", 0), ("q2", 1), ("q3", 2)]:
        d.click(f"input[name={question}][value='{choice}']")
    page.evaluate("window.scrollTo(0, 120)"); shot("07-quiz-in-progress")
    for question, choice in [("q4", 0), ("q5", 1)]:
        d.click(f"input[name={question}][value='{choice}']")
    d.click("#quiz-submit"); page.wait_for_timeout(1500); shot("08-quiz-result")
    d.goto("/activity"); shot("09-activity-log")
    d.goto("/activity?component=Video"); d.click("details.meta summary"); shot("10-activity-video-metadata")
    d.click("text=Log out"); d.login("instructor", "teach123")
    d.goto("/analytics"); shot("11-analytics")
    jump = "y => window.scrollTo({top: document.querySelector('#log').offsetTop + y, behavior: 'instant'})"
    page.evaluate(jump, -520); shot("12-analytics-learners")
    d.goto("/analytics?event_name=Quiz+attempt+submitted")
    page.evaluate(jump, 20); shot("13-analytics-log")
    context.close()


def main():
    DEMO.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(channel="chrome", args=["--autoplay-policy=no-user-gesture-required"])
        background_learners(browser)
        raw = recorded_walkthrough(browser, Path(tmp))
        screenshots(browser)
        browser.close()
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "slow",
                        "-crf", "26", "-pix_fmt", "yuv420p", "-r", "25", "-movflags", "+faststart", "-an",
                        str(DEMO / "learntrack-demo.mp4")], check=True)
    print("done")


if __name__ == "__main__":
    main()
