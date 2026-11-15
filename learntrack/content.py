"""Course content.

Each course has lessons; each lesson is a list of blocks. Block types:

* ``text``    - HTML reading material
* ``details`` - an expandable "dig deeper" section
* ``video``   - an MP4 in ``static/videos``
* ``check``   - a single inline knowledge-check question with instant feedback
* ``quiz``    - a graded multi-question quiz (attempts are stored)
"""

COURSES = [
    {
        "id": "learning-analytics",
        "title": "Learning Analytics Foundations",
        "summary": "What learner data is, how clickstream logs are captured, and how to turn "
                   "raw clicks into insight without losing sight of the learner's privacy.",
        "level": "Beginner",
        "accent": "teal",
        "lessons": [
            {
                "id": "what-is-la",
                "title": "What is learning analytics?",
                "minutes": 6,
                "blocks": [
                    {"type": "text", "html": """
<p class="lead">Every time you open a lesson, pause a video or submit a quiz, you leave a small
trace. <strong>Learning analytics</strong> is the practice of collecting those traces, analysing
them and using what they show to improve learning.</p>
<p>The most widely used definition comes from the first Learning Analytics and Knowledge
conference in 2011. In plain words, it describes four activities carried out on data about
learners and their contexts:</p>
<ol>
  <li><strong>Measurement</strong> &ndash; deciding what to observe (time on task, attempts, order of actions).</li>
  <li><strong>Collection</strong> &ndash; recording it reliably, usually as timestamped events.</li>
  <li><strong>Analysis</strong> &ndash; finding patterns such as who is stuck and where.</li>
  <li><strong>Reporting</strong> &ndash; showing the result to someone who can act on it.</li>
</ol>
<p>The goal is never the data itself. The goal is <em>understanding and improving learning and
the environments in which it happens</em>.</p>
<h3>Three kinds of questions</h3>
<table class="content-table">
  <tr><th>Type</th><th>Question it answers</th><th>Example</th></tr>
  <tr><td>Descriptive</td><td>What happened?</td><td>62% of learners finished the video.</td></tr>
  <tr><td>Predictive</td><td>What is likely to happen?</td><td>Learners who skip week 2 often drop out.</td></tr>
  <tr><td>Prescriptive</td><td>What should we do?</td><td>Send a reminder after three days of inactivity.</td></tr>
</table>
"""},
                    {"type": "details", "id": "la-vs-edm",
                     "summary": "Dig deeper: learning analytics vs educational data mining",
                     "html": """
<p>The two fields overlap heavily. A useful rule of thumb: <strong>educational data mining</strong>
leans towards automated discovery (algorithms find the pattern), while <strong>learning
analytics</strong> leans towards supporting human judgement (a teacher or learner looks at a
dashboard and decides). In practice most projects use both.</p>"""},
                    {"type": "check", "id": "la-check-1",
                     "question": "A dashboard that warns “this learner is likely to fail the next quiz” is an example of which type of analytics?",
                     "options": ["Descriptive", "Predictive", "Prescriptive"],
                     "answer": 1,
                     "explanation": "It estimates a future outcome from past data, which is predictive. "
                                    "It would become prescriptive if it also recommended an action."},
                    {"type": "text", "html": """
<h3>Where the data comes from</h3>
<p>Most learning data falls into one of these buckets:</p>
<ul>
  <li><strong>Clickstream / log data</strong> &ndash; every page view, click and media action (this app records these).</li>
  <li><strong>Assessment data</strong> &ndash; quiz answers, scores, number of attempts.</li>
  <li><strong>Learner-produced content</strong> &ndash; forum posts, essays, code.</li>
  <li><strong>Profile data</strong> &ndash; programme, prior grades, demographics.</li>
</ul>
<p>In the next lesson you will look closely at the first bucket &ndash; and at the exact rows this
app is writing about you right now. Open <a href="/activity">My activity</a> at any time to see them.</p>
"""},
                ],
            },
            {
                "id": "clickstream-explained",
                "title": "Clickstream data explained",
                "minutes": 7,
                "blocks": [
                    {"type": "text", "html": """
<p class="lead">A clickstream is the ordered list of everything a person does in an application.
Watch the short explainer, then read how a single row is put together.</p>"""},
                    {"type": "video", "id": "clickstream-explained", "src": "clickstream-explained.mp4",
                     "title": "Clickstream in one minute", "seconds": 60},
                    {"type": "text", "html": """
<h3>Anatomy of one event</h3>
<p>Learning platforms such as Moodle store each action as one row. This app uses the same
seven core columns:</p>
<table class="content-table">
  <tr><th>Column</th><th>Meaning</th><th>Example</th></tr>
  <tr><td>Time</td><td>When it happened</td><td>15/11/26, 10:42:07</td></tr>
  <tr><td>Event context</td><td>Where in the course</td><td>Lesson: Clickstream data explained</td></tr>
  <tr><td>Component</td><td>Which part of the system</td><td>Video</td></tr>
  <tr><td>Event name</td><td>What kind of action</td><td>Video paused</td></tr>
  <tr><td>Description</td><td>A readable sentence</td><td>User 7 paused video &lsquo;Clickstream in one minute&rsquo; at 0:21</td></tr>
  <tr><td>Origin</td><td>How it reached the server</td><td>web</td></tr>
  <tr><td>IP address</td><td>Network address of the device</td><td>10.17.35.67</td></tr>
</table>
<p>Extra detail that does not fit a column &ndash; the video position, the scroll depth, the
option chosen in a quiz &ndash; travels in a JSON <code>metadata</code> field.</p>"""},
                    {"type": "check", "id": "cs-check-1",
                     "question": "You pause the video above at 0:21. Which column tells an analyst that it was a pause rather than a play?",
                     "options": ["Event context", "Component", "Event name", "Origin"],
                     "answer": 2,
                     "explanation": "The event name (“Video paused”) identifies the action. "
                                    "The component only says it involved the video player."},
                    {"type": "details", "id": "client-vs-server",
                     "summary": "Dig deeper: client-side vs server-side tracking",
                     "html": """
<p><strong>Server-side</strong> events are recorded when a request reaches the server: logins,
page views, quiz submissions. They are reliable but blind to what happens inside a page.</p>
<p><strong>Client-side</strong> events are recorded by JavaScript in the browser: clicks,
scrolling, video play and pause. They are detailed, but they must be sent to the server in
batches and can be lost if the tab closes abruptly, which is why trackers use
<code>navigator.sendBeacon</code> on page exit. LearnTrack uses both.</p>"""},
                ],
            },
            {
                "id": "clicks-to-insights",
                "title": "From clicks to insights",
                "minutes": 4,
                "blocks": [
                    {"type": "video", "id": "clicks-to-insights", "src": "clicks-to-insights.mp4",
                     "title": "From clicks to insights", "seconds": 50},
                    {"type": "text", "html": """
<p>Try it yourself: play the video, pause it, drag the seek bar backwards and change the playback
speed. Then open <a href="/activity?component=Video">My activity &rarr; Video</a>. Each of those
actions is there, with the exact position in the video.</p>
<p>Re-watching the same 10 seconds three times is one of the strongest signals in video
analytics that a passage is confusing.</p>"""},
                ],
            },
            {
                "id": "ethics-privacy",
                "title": "Ethics and privacy of learner data",
                "minutes": 5,
                "blocks": [
                    {"type": "text", "html": """
<p class="lead">Being able to record everything does not mean you should. Learner data is
personal data, and the people it describes are often not in a position to refuse.</p>
<h3>Four working principles</h3>
<ul>
  <li><strong>Transparency</strong> &ndash; tell learners what is collected and why. (This app shows you your own log.)</li>
  <li><strong>Purpose limitation</strong> &ndash; use the data to support learning, not for unrelated judgement.</li>
  <li><strong>Data minimisation</strong> &ndash; collect what the purpose needs and no more. LearnTrack records <em>that</em> you typed in a field, never <em>what</em> you typed.</li>
  <li><strong>Access control</strong> &ndash; a learner sees only their own rows; only the instructor sees the class.</li>
</ul>"""},
                    {"type": "check", "id": "ethics-check-1",
                     "question": "A tracker records every keystroke in the login form, including passwords, “for completeness”. Which principle does this most clearly break?",
                     "options": ["Transparency", "Data minimisation", "Access control"],
                     "answer": 1,
                     "explanation": "Passwords are not needed to understand learning, so collecting them "
                                    "breaks data minimisation (and creates a serious security risk)."},
                    {"type": "details", "id": "consent",
                     "summary": "Dig deeper: is consent enough?",
                     "html": """
<p>Consent matters, but students rarely have a real choice when a course requires a platform.
That is why researchers argue for <em>ongoing</em> transparency and the right to see and
question one's own data, rather than a single “I agree” checkbox.</p>"""},
                ],
            },
            {
                "id": "la-quiz",
                "title": "Course quiz: Learning Analytics Foundations",
                "minutes": 5,
                "blocks": [
                    {"type": "quiz", "pass_mark": 60, "questions": [
                        {"id": "q1", "text": "Which list contains the four activities in the standard definition of learning analytics?",
                         "options": ["Measurement, collection, analysis, reporting",
                                     "Teaching, testing, grading, certifying",
                                     "Planning, coding, testing, deploying",
                                     "Storage, backup, encryption, deletion"],
                         "answer": 0,
                         "explanation": "Learning analytics is the measurement, collection, analysis and reporting of data about learners and their contexts."},
                        {"id": "q2", "text": "In a clickstream row, what does the “Event context” column record?",
                         "options": ["The learner's password", "Where in the course the action happened",
                                     "The browser version", "The score of the quiz"],
                         "answer": 1,
                         "explanation": "Event context locates the action, for example “Lesson: Clickstream data explained”."},
                        {"id": "q3", "text": "Why do browser trackers use sendBeacon when the page is closing?",
                         "options": ["It encrypts the data", "It makes the page load faster",
                                     "It lets queued events still reach the server during unload",
                                     "It blocks the user from leaving"],
                         "answer": 2,
                         "explanation": "sendBeacon queues a small request the browser will deliver even while the page unloads."},
                        {"id": "q4", "text": "A learner replays the same 10 seconds of a video three times. The most reasonable first interpretation is:",
                         "options": ["The learner is cheating", "The passage may be confusing or important",
                                     "The video file is corrupt", "The learner has finished the course"],
                         "answer": 1,
                         "explanation": "Repeated re-watching usually marks difficulty or importance. It is a signal to inspect the content, not to judge the learner."},
                        {"id": "q5", "text": "Which practice best follows the data minimisation principle?",
                         "options": ["Recording every keystroke in every form",
                                     "Recording that a field was used, but not what was typed",
                                     "Sharing all logs with every learner",
                                     "Keeping data forever in case it becomes useful"],
                         "answer": 1,
                         "explanation": "Collect only what the stated purpose needs."},
                    ]},
                ],
            },
        ],
    },
    {
        "id": "web-fundamentals",
        "title": "Web Fundamentals for Educational Apps",
        "summary": "The minimum web knowledge needed to build a learning app with a login: "
                   "requests and responses, sessions and cookies.",
        "level": "Beginner",
        "accent": "amber",
        "lessons": [
            {
                "id": "how-the-web-works",
                "title": "How the web works",
                "minutes": 5,
                "blocks": [
                    {"type": "text", "html": """
<p class="lead">A web app is a conversation between two programs: a <strong>client</strong>
(your browser) that asks, and a <strong>server</strong> that answers.</p>
<ol>
  <li>You type an address or click a link.</li>
  <li>The browser sends an <strong>HTTP request</strong> to the server.</li>
  <li>The server runs code, often reading a database, and sends back an <strong>HTTP response</strong>.</li>
  <li>The browser renders the HTML, then runs any JavaScript on the page.</li>
</ol>
<p>In LearnTrack the server is a Python program written with Flask, and the database is a single
SQLite file. Nothing else needs to be installed.</p>"""},
                    {"type": "check", "id": "web-check-1",
                     "question": "Which side stores the course content and the clickstream table?",
                     "options": ["The client (browser)", "The server"],
                     "answer": 1,
                     "explanation": "The server owns the database. The browser only holds what the server sends to it."},
                ],
            },
            {
                "id": "http-in-60-seconds",
                "title": "HTTP in 60 seconds",
                "minutes": 4,
                "blocks": [
                    {"type": "video", "id": "http-in-60-seconds", "src": "http-in-60-seconds.mp4",
                     "title": "HTTP in 60 seconds", "seconds": 60},
                    {"type": "text", "html": """
<h3>The two methods you meet first</h3>
<table class="content-table">
  <tr><th>Method</th><th>Purpose</th><th>In this app</th></tr>
  <tr><td><code>GET</code></td><td>Read something</td><td><code>GET /course/web-fundamentals</code> shows this course</td></tr>
  <tr><td><code>POST</code></td><td>Send something</td><td><code>POST /api/events</code> stores a batch of clicks</td></tr>
</table>"""},
                    {"type": "check", "id": "http-check-1",
                     "question": "The server answers with status code 404. What does that mean?",
                     "options": ["Everything worked", "The address was not found", "You must log in first"],
                     "answer": 1,
                     "explanation": "404 means “not found”. 200 means OK, and 401/403 are about permission."},
                ],
            },
            {
                "id": "sessions-and-login",
                "title": "Sessions, cookies and login",
                "minutes": 5,
                "blocks": [
                    {"type": "text", "html": """
<p class="lead">HTTP forgets you after every request. A login only works because the browser
reminds the server who you are, each time, with a <strong>cookie</strong>.</p>
<h3>What happens when you log in</h3>
<ol>
  <li>You send your username and password with a <code>POST</code>.</li>
  <li>The server compares the password against a stored <strong>hash</strong> (never the plain password).</li>
  <li>If it matches, the server sends back a signed <strong>session cookie</strong>.</li>
  <li>The browser attaches that cookie to every later request, so the server knows which learner is asking.</li>
</ol>
<p>The same session is what lets a tracker attach <em>your</em> user id to each click.</p>"""},
                    {"type": "details", "id": "hashing",
                     "summary": "Dig deeper: why hash passwords?",
                     "html": """
<p>A hash is a one-way fingerprint. If the database leaks, attackers get fingerprints, not
passwords. A good scheme also adds a random <em>salt</em> so two people with the same password
get different hashes. LearnTrack uses Werkzeug's salted <code>scrypt</code> hashes.</p>"""},
                    {"type": "check", "id": "session-check-1",
                     "question": "What does the server store so it can check your password later?",
                     "options": ["The password itself", "A salted hash of the password", "Nothing"],
                     "answer": 1,
                     "explanation": "Only a salted hash is stored, so the original password cannot be read back."},
                ],
            },
            {
                "id": "web-quiz",
                "title": "Course quiz: Web Fundamentals",
                "minutes": 4,
                "blocks": [
                    {"type": "quiz", "pass_mark": 60, "questions": [
                        {"id": "q1", "text": "In a web app, which program sends the HTTP request?",
                         "options": ["The database", "The client (browser)", "The server", "The cookie"],
                         "answer": 1,
                         "explanation": "The client asks; the server answers."},
                        {"id": "q2", "text": "Which HTTP method is meant for sending new data, such as a batch of click events?",
                         "options": ["GET", "POST", "HEAD", "OPTIONS"],
                         "answer": 1,
                         "explanation": "POST carries data to the server. GET only reads."},
                        {"id": "q3", "text": "How does the server recognise a logged-in learner on later requests?",
                         "options": ["It remembers the IP address", "The browser sends the session cookie each time",
                                     "The learner types the password on every page", "It cannot"],
                         "answer": 1,
                         "explanation": "The session cookie is attached to every request automatically."},
                        {"id": "q4", "text": "Status code 200 means:",
                         "options": ["OK", "Not found", "Server error", "Redirect"],
                         "answer": 0,
                         "explanation": "200 is the standard success response."},
                    ]},
                ],
            },
        ],
    },
]


def get_course(course_id):
    return next((c for c in COURSES if c["id"] == course_id), None)


def get_lesson(course_id, lesson_id):
    course = get_course(course_id)
    if not course:
        return None, None
    return course, next((l for l in course["lessons"] if l["id"] == lesson_id), None)


def find_lesson(lesson_id):
    """Look a lesson up by id alone (lesson ids are unique across courses)."""
    for course in COURSES:
        for lesson in course["lessons"]:
            if lesson["id"] == lesson_id:
                return course, lesson
    return None, None


def lesson_kind(lesson) -> str:
    """Label shown on the course page: Text, Video, Quiz or Text + Video."""
    types = {b["type"] for b in lesson["blocks"]}
    if "quiz" in types:
        return "Quiz"
    if "video" in types:
        reading_blocks = sum(b["type"] in ("text", "details", "check") for b in lesson["blocks"])
        return "Text + Video" if reading_blocks > 1 else "Video"
    return "Text"


def get_block(lesson, block_type, block_id=None):
    for block in lesson["blocks"]:
        if block["type"] == block_type and (block_id is None or block.get("id") == block_id):
            return block
    return None


def total_lessons() -> int:
    return sum(len(c["lessons"]) for c in COURSES)
