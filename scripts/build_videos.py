"""Build the three lesson videos from HTML slides.

Development tool only (the finished MP4s are committed under
learntrack/static/videos). Needs Playwright with Chrome and ffmpeg:

    pip install playwright && python scripts/build_videos.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "learntrack" / "static" / "videos"
SECONDS_PER_SLIDE = 10
FADE = 0.5

CSS = """
*{box-sizing:border-box;margin:0}
body{width:1280px;height:720px;background:#16222b;color:#f5f1e8;font-family:Georgia,'Palatino Linotype',serif;
  padding:70px 90px;display:flex;flex-direction:column;justify-content:center;position:relative;overflow:hidden}
body::before{content:"";position:absolute;right:-140px;top:-140px;width:420px;height:420px;border-radius:50%;background:ACCENT;opacity:.16}
.kicker{font:600 20px Arial,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:ACCENT;margin-bottom:22px}
h1{font-size:74px;line-height:1.08;font-weight:600;max-width:980px}
h2{font-size:50px;line-height:1.15;font-weight:600;max-width:1040px;margin-bottom:34px}
p{font:28px/1.45 Arial,sans-serif;color:#c9d3da;max-width:1000px}
.sub{font:30px/1.4 Arial,sans-serif;color:#c9d3da;margin-top:26px}
.row{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-top:8px}
.pill{font:600 26px Arial,sans-serif;background:#24343f;border:2px solid #3a4e5b;border-radius:99px;padding:14px 26px}
.arrow{font:32px Arial;color:ACCENT}
.cols{display:flex;gap:32px;margin-top:6px}
.box{flex:1;background:#1f2e38;border:2px solid #34485564;border-top:6px solid ACCENT;border-radius:14px;padding:26px 30px}
.box h3{font-size:34px;margin-bottom:12px}
.box p,.box li{font:25px/1.5 Arial,sans-serif;color:#c9d3da}
.box ul{padding-left:26px}
table{border-collapse:collapse;font:24px Arial,sans-serif;width:100%;margin-top:6px}
th{font-size:17px;letter-spacing:.1em;text-transform:uppercase;color:ACCENT;text-align:left;padding:10px 16px}
td{background:#1f2e38;padding:16px;border-top:2px solid #16222b}
code,.mono{font-family:Menlo,Consolas,'DejaVu Sans Mono',monospace}
.code{font:30px/1.5 Menlo,Consolas,'DejaVu Sans Mono',monospace;background:#0f181e;border-radius:12px;padding:24px 30px;color:#e8a94c;margin-top:6px}
.code span{color:#8fa1ad}
.bars div{display:flex;align-items:center;gap:18px;font:24px Arial,sans-serif;margin:14px 0}
.bars i{display:block;height:30px;background:ACCENT;border-radius:6px}
.bars b{width:250px;font-weight:400;color:#c9d3da}
.foot{position:absolute;left:90px;bottom:38px;font:18px Arial,sans-serif;color:#7d8d98;letter-spacing:.06em}
.n{position:absolute;right:90px;bottom:38px;font:18px Arial,sans-serif;color:#7d8d98}
"""

VIDEOS = {
    "clickstream-explained": ("Clickstream in one minute", "#3fb5a8", [
        '<div class="kicker">Learning Analytics Foundations</div><h1>Clickstream in one minute</h1><p class="sub">What an app remembers about what you do</p>',
        '<h2>A clickstream is the ordered trail of actions a person takes in an app.</h2><div class="row"><span class="pill">Log in</span><span class="arrow">→</span><span class="pill">Open lesson</span><span class="arrow">→</span><span class="pill">Play video</span><span class="arrow">→</span><span class="pill">Pause</span><span class="arrow">→</span><span class="pill">Answer quiz</span></div>',
        '<h2>Each action becomes one row.</h2><table><tr><th>Time</th><th>Event context</th><th>Component</th><th>Event name</th></tr><tr><td>10:42:07</td><td>Lesson: Clickstream data</td><td>Video</td><td>Video played</td></tr><tr><td>10:42:28</td><td>Lesson: Clickstream data</td><td>Video</td><td>Video paused</td></tr><tr><td>10:43:02</td><td>Quiz: Course quiz</td><td>Quiz</td><td>Quiz attempt started</td></tr></table>',
        '<h2>Events are captured in two places.</h2><div class="cols"><div class="box"><h3>In the browser</h3><ul><li>clicks and scrolling</li><li>video play, pause, seek</li><li>answers being selected</li></ul></div><div class="box"><h3>On the server</h3><ul><li>logins and logouts</li><li>page views</li><li>quiz scores</li></ul></div></div>',
        '<h2>The browser sends events in small batches.</h2><div class="row"><span class="pill">Event queue</span><span class="arrow">→</span><span class="pill mono">POST /api/events</span><span class="arrow">→</span><span class="pill">Database table</span></div><p class="sub">On page exit, a beacon delivers whatever is still queued.</p>',
        '<div class="kicker">Try it now</div><h2>Pause this video.</h2><p>That pause has just been recorded with the exact position in the video. Open <b>My activity</b> to find the row.</p>',
    ]),
    "clicks-to-insights": ("From clicks to insights", "#a99be0", [
        '<div class="kicker">Learning Analytics Foundations</div><h1>From clicks to insights</h1><p class="sub">Three things you can do with a table of events</p>',
        '<h2>1. Count them: where is the activity?</h2><div class="bars"><div><b>Lesson 1 · text</b><i style="width:420px"></i>42</div><div><b>Lesson 2 · video</b><i style="width:610px"></i>61</div><div><b>Lesson 3 · video</b><i style="width:230px"></i>23</div><div><b>Quiz</b><i style="width:350px"></i>35</div></div>',
        '<h2>2. Order them: what did the learner do?</h2><div class="row"><span class="pill">Play</span><span class="arrow">→</span><span class="pill">Skip back 10 s</span><span class="arrow">→</span><span class="pill">Play</span><span class="arrow">→</span><span class="pill">Skip back 10 s</span></div><p class="sub">Replaying the same passage is a sign that it is confusing or important.</p>',
        '<h2>3. Combine them: who needs help?</h2><div class="cols"><div class="box"><h3>Clickstream</h3><p>Stopped the video at 0:15 and never opened lesson 3.</p></div><div class="box"><h3>Assessment</h3><p>Scored 2 out of 5 on the course quiz, twice.</p></div></div>',
        '<div class="kicker">Remember</div><h2>An insight is a question answered, not a chart.</h2><p>Start from what a teacher or learner needs to decide, then look for the events that can answer it.</p>',
    ]),
    "http-in-60-seconds": ("HTTP in 60 seconds", "#e8a94c", [
        '<div class="kicker">Web Fundamentals</div><h1>HTTP in 60 seconds</h1><p class="sub">How a browser and a server talk</p>',
        '<h2>One side asks. The other answers.</h2><div class="row"><span class="pill">Client (browser)</span><span class="arrow">— request →</span><span class="pill">Server</span></div><div class="row" style="margin-top:22px"><span class="pill">Client (browser)</span><span class="arrow">← response —</span><span class="pill">Server</span></div>',
        '<h2>A request names a method and a path.</h2><div class="code">GET /course/web-fundamentals HTTP/1.1<br><span>Host: localhost:5000<br>Cookie: session=…</span></div><p class="sub"><b>GET</b> reads something. <b>POST</b> sends something.</p>',
        '<h2>A response carries a status and a body.</h2><div class="code">HTTP/1.1 200 OK<br><span>Content-Type: text/html</span><br><br>&lt;!doctype html&gt; …</div>',
        '<h2>Status codes you will meet.</h2><table><tr><th>Code</th><th>Meaning</th></tr><tr><td>200</td><td>OK: here is what you asked for</td></tr><tr><td>302</td><td>Redirect: go to another address</td></tr><tr><td>403</td><td>Forbidden: you may not see this</td></tr><tr><td>404</td><td>Not found</td></tr></table>',
        '<div class="kicker">One catch</div><h2>HTTP forgets you after every request.</h2><p>A cookie sent with each request is what keeps you logged in. That is the next lesson.</p>',
    ]),
}


def build(name, title, accent, slides, browser, tmp):
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    frames = []
    for i, body in enumerate(slides, 1):
        html = (f"<style>{CSS.replace('ACCENT', accent)}</style>{body}"
                f'<div class="foot">LEARNTRACK · {title.upper()}</div><div class="n">{i} / {len(slides)}</div>')
        page.set_content(html)
        frame = tmp / f"{name}-{i}.png"
        page.screenshot(path=str(frame))
        frames.append(frame)
    page.close()

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for frame in frames:
        cmd += ["-loop", "1", "-t", str(SECONDS_PER_SLIDE + FADE), "-i", str(frame)]
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono"]
    chain, last = [], "[0:v]"
    for i in range(1, len(frames)):
        out = f"[v{i}]"
        chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={FADE}:offset={i * SECONDS_PER_SLIDE}{out}")
        last = out
    total = len(frames) * SECONDS_PER_SLIDE
    cmd += ["-filter_complex", ";".join(chain), "-map", last, "-map", f"{len(frames)}:a", "-t", str(total),
            "-r", "24", "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "32k", "-movflags", "+faststart", str(OUT / f"{name}.mp4")]
    subprocess.run(cmd, check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(frames[0]), "-q:v", "4", str(OUT / f"{name}.jpg")], check=True)
    print(f"built {name}.mp4 ({total}s)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(channel="chrome")
        for name, (title, accent, slides) in VIDEOS.items():
            build(name, title, accent, slides, browser, Path(tmp))
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
