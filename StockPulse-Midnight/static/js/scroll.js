/* StockPulse · subtle, one-time scroll reveals. No content is hidden by CSS. */
(() => {
  'use strict';
  if (!('IntersectionObserver' in window) || !Element.prototype.animate) return;
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const seen = new WeakSet();
  const active = new Map();
  let observer;

  // Keep input areas, sticky settings, charts' internals and dialogs untouched.
  const candidates = [...document.querySelectorAll(
    '.page-head, .hero > div, .feature-card, .content .card, .auth-story > h1, .auth-story > .lead'
  )].filter(element =>
    !element.matches('.chat-panel, .settings-layout > .card') &&
    !element.closest('dialog') && !element.querySelector('form')
  );
  const targets = candidates.filter(element =>
    !candidates.some(parent => parent !== element && parent.contains(element))
  );

  function finish(element) {
    seen.add(element);
    observer?.unobserve(element);
    const animation = active.get(element);
    if (animation) {
      active.delete(element);
      animation.cancel();
    }
  }

  function stop() {
    observer?.disconnect();
    for (const element of [...active.keys()]) finish(element);
  }

  function start() {
    stop();
    if (preference.matches || document.hidden) return;
    const compact = window.matchMedia('(max-width: 650px)').matches;
    observer = new IntersectionObserver(entries => {
      // Only stagger cards entering together; do not delay later scroll sections.
      const visible = entries.filter(entry => entry.isIntersecting && !seen.has(entry.target))
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top ||
          a.boundingClientRect.left - b.boundingClientRect.left);
      visible.forEach((entry, index) => {
        const element = entry.target;
        seen.add(element);
        observer.unobserve(element);
        // Jump links or keyboard focus must never wait for an animation.
        if (element.contains(document.activeElement)) return;
        try {
          const animation = element.animate([
            { opacity: 0.45, transform: `translateY(${compact ? 8 : 14}px)` },
            { opacity: 1, transform: 'translateY(0)' }
          ], {
            duration: compact ? 340 : 480,
            delay: Math.min(index, compact ? 2 : 3) * (compact ? 35 : 55),
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            fill: 'none'
          });
          active.set(element, animation);
          const cleanup = () => {
            if (active.get(element) === animation) active.delete(element);
          };
          animation.addEventListener('finish', cleanup, { once: true });
          animation.addEventListener('cancel', cleanup, { once: true });
        } catch (_) {
          // Unsupported or interrupted animations leave the default visible layout.
        }
      });
    }, { threshold: 0.04, rootMargin: '0px 0px -20px 0px' });
    targets.forEach(element => {
      element.dataset.scrollReveal = '';
      if (!seen.has(element)) observer.observe(element);
    });
  }

  // Interacting with a card immediately removes any motion on that card.
  const settleInteraction = event => {
    const element = event.target.closest?.('[data-scroll-reveal]');
    if (element) finish(element);
  };
  document.addEventListener('focusin', settleInteraction);
  document.addEventListener('pointerdown', settleInteraction, { passive: true });
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  window.addEventListener('pagehide', stop);
  window.addEventListener('pageshow', start);
  if (preference.addEventListener) preference.addEventListener('change', start);
  else preference.addListener(start);
  start();
})();
