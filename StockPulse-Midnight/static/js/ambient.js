/* Decorative finance footage. Poster-first, muted, pausable and motion-aware. */
(() => {
  'use strict';
  const scene = document.getElementById('ambientScene');
  const video = document.getElementById('ambientVideo');
  const button = document.getElementById('motionToggle');
  const label = document.getElementById('motionLabel');
  if (!scene || !video || !button || !label) return;
  const chatToolbar = document.querySelector('.chat-heading');
  if (chatToolbar) { button.classList.add('motion-toggle-inline'); chatToolbar.append(button); }
  else if (document.querySelector('.topbar-right')) {
    button.classList.add('motion-toggle-inline', 'motion-toggle-header');
    document.querySelector('.topbar-right').prepend(button);
  } else if (document.querySelector('.auth-story')) {
    button.classList.add('motion-toggle-auth');
    document.querySelector('.auth-story').append(button);
  }
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection;
  let userPaused = false;
  let dataConsent = false;
  let pending = false;
  let frame = 0;
  let failed = false;
  try { userPaused = localStorage.getItem('stockpulse-background-paused') === '1'; } catch (_) {}
  video.muted = true;
  video.defaultMuted = true;
  video.disablePictureInPicture = true;

  function display() {
    const off = reduced.matches;
    const playing = !video.paused && !off;
    button.hidden = failed;
    button.disabled = off;
    button.setAttribute('aria-label', off ? 'Background motion disabled by your system preference' : playing ? 'Pause background video' : 'Play background video');
    button.title = button.getAttribute('aria-label');
    label.textContent = off ? 'Motion off' : playing ? 'Pause background' : 'Play background';
    button.dataset.playing = playing ? 'true' : 'false';
  }
  async function update() {
    if (failed) return;
    const saveData = !!connection?.saveData && !dataConsent;
    if (reduced.matches || userPaused || saveData || document.hidden) {
      video.pause();
      if (reduced.matches) scene.classList.remove('video-ready');
      display();
      return;
    }
    if (!video.getAttribute('src')) {
      const supportsMP4 = video.canPlayType('video/mp4; codecs="avc1.64001f"');
      video.src = supportsMP4 ? video.dataset.src : video.dataset.webm;
      video.load();
    }
    if (pending) return;
    pending = true;
    try {
      await video.play();
      if (reduced.matches || userPaused || document.hidden) video.pause();
    } catch (_) {
      // Autoplay denial is harmless: the matching still image stays visible.
    } finally {
      pending = false;
      display();
    }
  }
  video.addEventListener('playing', () => {
    if (reduced.matches || userPaused || document.hidden) { video.pause(); return; }
    scene.classList.add('video-ready');
    display();
  });
  video.addEventListener('pause', display);
  video.addEventListener('error', () => {
    failed = true;
    scene.classList.remove('video-ready');
    video.pause();
    display();
  });
  button.addEventListener('click', () => {
    if (reduced.matches) return;
    if (!video.paused) userPaused = true;
    else { userPaused = false; dataConsent = true; }
    try { localStorage.setItem('stockpulse-background-paused', userPaused ? '1' : '0'); } catch (_) {}
    update();
  });

  // A small compositor-only shift adds depth without changing native scrolling.
  function position() {
    frame = 0;
    const ratio = Math.min(1, scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight));
    scene.style.setProperty('--scene-shift', reduced.matches ? '0px' : `${-ratio * 18}px`);
  }
  function onScroll() {
    if (!reduced.matches && !frame) frame = requestAnimationFrame(position);
  }
  addEventListener('scroll', onScroll, { passive: true });
  addEventListener('resize', position, { passive: true });
  addEventListener('pagehide', () => { video.pause(); if (frame) cancelAnimationFrame(frame); frame = 0; });
  addEventListener('pageshow', () => { position(); update(); });
  document.addEventListener('visibilitychange', update);
  const preferenceChanged = () => { position(); update(); };
  if (reduced.addEventListener) reduced.addEventListener('change', preferenceChanged);
  else reduced.addListener(preferenceChanged);
  connection?.addEventListener?.('change', update);
  position();
  update();
})();
