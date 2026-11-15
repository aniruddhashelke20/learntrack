/*
 * Lesson page behaviour: video tracking, inline knowledge checks,
 * expandable sections, lesson completion and the quiz flow.
 */
(function () {
  'use strict';

  var LT = window.LearnTrack;
  var lessonEl = document.querySelector('.lesson');
  if (!LT || !lessonEl) return;
  var lessonId = lessonEl.dataset.lessonId;

  function clock(seconds) {
    seconds = Math.max(0, Math.floor(seconds || 0));
    return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  }
  function round1(n) { return Math.round((n || 0) * 10) / 10; }

  /* ------------------------------------------------------------ video ---- */
  document.querySelectorAll('video[data-video-id]').forEach(function (video) {
    var id = video.dataset.videoId;
    var title = video.dataset.videoTitle;
    var figure = video.closest('figure');
    var lastTime = 0;        // last known position while playing normally
    var seekFrom = null;
    var watched = 0;         // seconds actually played (not skipped)
    var milestones = {};
    var volumeTimer = null;
    var wasMuted = video.muted;
    var inFullscreen = false;

    function send(name, action, extra) {
      var meta = { video_id: id, position: round1(video.currentTime), duration: round1(video.duration),
                   playback_rate: video.playbackRate, seconds_watched: round1(watched) };
      for (var key in (extra || {})) if (key !== 'suffix') meta[key] = extra[key];
      LT.track(name, action + " video '" + title + "'" + (extra && extra.suffix ? extra.suffix : ' at ' + clock(video.currentTime)),
               { component: 'Video', metadata: meta });
    }

    video.addEventListener('play', function () {
      send('Video played', video.currentTime < 0.5 ? 'started playing' : 'resumed');
    });
    video.addEventListener('pause', function () {
      if (video.ended || video.seeking) return;
      send('Video paused', 'paused');
    });
    video.addEventListener('timeupdate', function () {
      if (video.seeking) return;
      var delta = video.currentTime - lastTime;
      var playing = !video.paused && delta > 0 && delta < 1.5;
      if (playing) watched += delta;
      lastTime = video.currentTime;
      // Milestones count only when reached by playing, not by dragging the seek bar past them.
      if (playing) [25, 50, 75].forEach(function (mark) {
        if (!milestones[mark] && video.duration && video.currentTime / video.duration * 100 >= mark) {
          milestones[mark] = true;
          send('Video progress reached', 'reached ' + mark + '% of', { percent: mark });
        }
      });
    });
    video.addEventListener('seeking', function () {
      if (seekFrom === null) seekFrom = lastTime;
    });
    video.addEventListener('seeked', function () {
      var from = seekFrom === null ? lastTime : seekFrom;
      seekFrom = null;
      lastTime = video.currentTime;
      if (Math.abs(video.currentTime - from) < 0.5) return;
      send('Video seeked', video.currentTime < from ? 'skipped back in' : 'skipped ahead in',
           { from: round1(from), to: round1(video.currentTime),
             suffix: ' from ' + clock(from) + ' to ' + clock(video.currentTime) });
    });
    video.addEventListener('ratechange', function () {
      send('Video speed changed', 'changed the speed of', { suffix: ' to ' + video.playbackRate + 'x' });
      if (figure) figure.querySelectorAll('[data-speed]').forEach(function (b) {
        b.classList.toggle('is-on', Number(b.dataset.speed) === video.playbackRate);
      });
    });
    video.addEventListener('volumechange', function () {
      clearTimeout(volumeTimer);   // dragging the slider fires many events; keep the last
      volumeTimer = setTimeout(function () {
        if (video.muted !== wasMuted) {
          wasMuted = video.muted;
          send(video.muted ? 'Video muted' : 'Video unmuted', video.muted ? 'muted' : 'unmuted');
        } else {
          send('Video volume changed', 'changed the volume of',
               { volume: round1(video.volume), suffix: ' to ' + Math.round(video.volume * 100) + '%' });
        }
      }, 400);
    });
    video.addEventListener('ended', function () {
      send('Video completed', 'finished watching', { suffix: ' (' + Math.round(watched) + 's watched)' });
    });
    document.addEventListener('fullscreenchange', function () {
      var now = document.fullscreenElement === video;
      if (now !== inFullscreen) {
        inFullscreen = now;
        send(now ? 'Video fullscreen entered' : 'Video fullscreen exited', now ? 'entered fullscreen for' : 'left fullscreen for');
      }
    });

    if (figure) {
      figure.querySelectorAll('[data-speed]').forEach(function (button) {
        button.addEventListener('click', function () { video.playbackRate = Number(button.dataset.speed); });
      });
      var rewind = figure.querySelector('[data-rewind]');
      if (rewind) rewind.addEventListener('click', function () {
        video.currentTime = Math.max(0, video.currentTime - Number(rewind.dataset.rewind));
      });
    }
  });

  /* ------------------------------------------------- expandable text ---- */
  document.querySelectorAll('details[data-details-id]').forEach(function (details) {
    details.addEventListener('toggle', function () {
      var title = details.querySelector('summary').textContent.trim();
      LT.track(details.open ? 'Section expanded' : 'Section collapsed',
               (details.open ? 'expanded' : 'collapsed') + " the section '" + title + "'",
               { component: 'Text', metadata: { section_id: details.dataset.detailsId, open: details.open } });
    });
  });

  /* -------------------------------------------------- knowledge checks ---- */
  document.querySelectorAll('.check').forEach(function (check) {
    var feedback = check.querySelector('.feedback');
    var tries = 0;
    check.querySelectorAll('.option').forEach(function (button) {
      button.addEventListener('click', function () {
        tries += 1;
        LT.post('/api/lesson/' + lessonId + '/check/' + check.dataset.checkId, { choice: Number(button.dataset.choice) })
          .then(function (result) {
            feedback.hidden = false;
            button.classList.add(result.correct ? 'is-right' : 'is-wrong');
            if (result.correct) {
              feedback.className = 'feedback is-right';
              feedback.textContent = '✓ Correct' + (tries > 1 ? ' (attempt ' + tries + ')' : '') + '. ' + result.explanation;
              check.querySelectorAll('.option').forEach(function (b) { b.disabled = true; });
            } else {
              feedback.className = 'feedback is-wrong';
              feedback.textContent = '✗ Not quite. Have another look and try again.';
              button.disabled = true;
            }
          })
          .catch(function (err) { feedback.hidden = false; feedback.textContent = err.message; });
      });
    });
  });

  /* --------------------------------------------------- lesson complete ---- */
  var completeBtn = document.getElementById('complete-btn');
  function showDone() {
    var pill = document.getElementById('done-pill');
    if (pill) { pill.textContent = '✓ Complete'; pill.classList.add('is-done'); }
    if (completeBtn) { completeBtn.textContent = '✓ Completed'; completeBtn.disabled = true; }
  }
  if (completeBtn) completeBtn.addEventListener('click', function () {
    LT.post('/api/lesson/' + lessonId + '/complete').then(showDone);
  });

  /* --------------------------------------------------------------- quiz ---- */
  var quiz = document.getElementById('quiz');
  if (!quiz) return;
  var intro = document.getElementById('quiz-intro');
  var form = document.getElementById('quiz-form');
  var resultBox = document.getElementById('quiz-result');
  var warning = document.getElementById('quiz-warning');
  var attemptId = null;
  var chosen = {};

  document.getElementById('quiz-start').addEventListener('click', function () {
    LT.post('/api/quiz/' + lessonId + '/start').then(function (data) {
      attemptId = data.attempt_id;
      intro.hidden = true;
      form.hidden = false;
      form.querySelector('input').focus();
    });
  });

  form.addEventListener('change', function (event) {
    var input = event.target;
    if (input.type !== 'radio') return;
    var previous = chosen[input.name];
    chosen[input.name] = Number(input.value);
    warning.hidden = true;
    LT.track('Quiz answer selected',
      (previous === undefined ? 'selected' : 'changed the answer to') + ' option ' + (Number(input.value) + 1) +
      " for question '" + input.name + "' in attempt " + attemptId + " of quiz '" + lessonId + "'",
      { component: 'Quiz', metadata: { attempt_id: attemptId, question_id: input.name, choice: Number(input.value),
                                       changed_from: previous === undefined ? null : previous } });
  });

  function showResults(data, reviewing) {
    form.hidden = false;
    intro.hidden = true;
    data.results.forEach(function (r) {
      var fieldset = form.querySelector('[data-question-id="' + r.id + '"]');
      fieldset.classList.add(r.correct ? 'is-right' : 'is-wrong');
      fieldset.querySelectorAll('input').forEach(function (input) {
        var value = Number(input.value);
        input.disabled = true;
        input.checked = value === r.chosen;
        input.parentElement.classList.toggle('is-answer', value === r.answer);
        input.parentElement.classList.toggle('is-chosen-wrong', value === r.chosen && !r.correct);
      });
      var feedback = fieldset.querySelector('.feedback');
      feedback.hidden = false;
      feedback.className = 'feedback ' + (r.correct ? 'is-right' : 'is-wrong');
      feedback.textContent = (r.correct ? '✓ Correct. ' : r.chosen === null || r.chosen === undefined ? '✗ Not answered. ' : '✗ Incorrect. ') + r.explanation;
    });
    document.getElementById('quiz-submit').hidden = true;
    resultBox.hidden = false;
    document.getElementById('result-label').textContent = reviewing ? 'Reviewing a previous attempt' : 'Attempt submitted';
    document.getElementById('result-score').textContent = data.score + ' / ' + data.max_score + '  (' + data.percent + '%)';
    var passMark = Number(quiz.dataset.passMark);
    var passed = data.percent >= passMark;
    resultBox.classList.toggle('is-pass', passed);
    document.getElementById('result-text').textContent = passed
      ? 'Passed. This lesson is now marked complete.'
      : 'Below the ' + passMark + '% pass mark. Review the explanations and try again.';
    if (passed && !reviewing) showDone();
    resultBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var total = form.querySelectorAll('fieldset').length;
    if (Object.keys(chosen).length < total) { warning.hidden = false; return; }
    LT.post('/api/quiz/' + lessonId + '/submit', { attempt_id: attemptId, answers: chosen })
      .then(function (data) { showResults(data, false); })
      .catch(function (err) { warning.hidden = false; warning.textContent = err.message; });
  });

  document.querySelectorAll('[data-review]').forEach(function (button) {
    button.addEventListener('click', function () {
      fetch('/api/quiz/attempt/' + button.dataset.review, { credentials: 'same-origin' })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          form.querySelectorAll('fieldset').forEach(function (f) { f.classList.remove('is-right', 'is-wrong'); });
          showResults(data, true);
        });
    });
  });
})();
