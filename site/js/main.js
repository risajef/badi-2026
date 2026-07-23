'use strict';

// -----------------------------------------------------------------------------
// Anchor & Smooth Navigation
// -----------------------------------------------------------------------------

// Ensure scroll restoration is handled gracefully without breaking deep links.
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual';
}

function handleInitialScroll() {
  if (location.hash) {
    const targetEl = document.querySelector(location.hash);
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth' });
      return;
    }
  }
  window.scrollTo(0, 0);
}

document.addEventListener('DOMContentLoaded', handleInitialScroll);

// -----------------------------------------------------------------------------
// Interactive Poster Behaviour
// -----------------------------------------------------------------------------

(function initInteractivePoster() {
  const poster = document.getElementById('poster');
  const ball = document.getElementById('ball');
  const legs = document.getElementById('woman-legs');

  if (!poster || !ball || !legs) return;

  // Ball's resting spot (in the man's hands), as fractions of the poster box.
  const BALL_REST = { x: 0.788427 + 0.071854 / 2, y: 0.352381 + 0.050904 / 2 };

  // Proximity trigger radii (% of poster width)
  const BALL_RADIUS = 0.14;
  const LEGS_RADIUS = 0.16;

  function distance(ax, ay, bx, by) {
    const dx = ax - bx;
    const dy = ay - by;
    return Math.sqrt(dx * dx + dy * dy);
  }

  let rafPending = false;
  let lastClientX = 0;
  let lastClientY = 0;

  function updatePointerEffect() {
    rafPending = false;
    const rect = poster.getBoundingClientRect();
    if (rect.width === 0) return;

    const px = (lastClientX - rect.left) / rect.width;
    const py = (lastClientY - rect.top) / rect.height;

    // Ball: fly to woman's hands when pointer nears resting spot
    const ballDist = distance(px, py, BALL_REST.x, BALL_REST.y);
    ball.classList.toggle('is-away', ballDist < BALL_RADIUS);

    // Legs: wiggle when pointer nears legs center
    const legsRect = legs.getBoundingClientRect();
    const legsCx = (legsRect.left + legsRect.width / 2 - rect.left) / rect.width;
    const legsCy = (legsRect.top + legsRect.height / 2 - rect.top) / rect.height;
    const legsDist = distance(px, py, legsCx, legsCy);
    legs.classList.toggle('is-wiggle', legsDist < LEGS_RADIUS);
  }

  function handlePointerMove(event) {
    lastClientX = event.clientX;
    lastClientY = event.clientY;
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(updatePointerEffect);
    }
  }

  function resetPosterEffects() {
    ball.classList.remove('is-away');
    legs.classList.remove('is-wiggle');
  }

  // Interactive water ripple on tap/click (3 concentric oval rings)
  poster.addEventListener('pointerdown', (e) => {
    const rect = poster.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    for (let i = 0; i < 3; i++) {
      setTimeout(() => {
        const ripple = document.createElement('span');
        ripple.className = 'poster-ripple';
        ripple.style.left = `${x}px`;
        ripple.style.top = `${y}px`;
        poster.appendChild(ripple);
        setTimeout(() => ripple.remove(), 900);
      }, i * 140);
    }
  });

  const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  if (canHover) {
    poster.addEventListener('pointermove', handlePointerMove);
    poster.addEventListener('pointerleave', resetPosterEffects);
  } else {
    // Touch Devices: Cycle animations automatically when poster is visible
    const BALL_HOLD = 1800;
    const BALL_PAUSE = 3000;
    const LEGS_HOLD = 1300;
    const LEGS_PAUSE = 2500;
    const LEGS_START_DELAY = 900;

    let isPosterVisible = false;
    let ballTimer = null;
    let legsTimer = null;

    function runBallCycle() {
      if (!isPosterVisible) return;
      ball.classList.add('is-away');
      setTimeout(() => ball.classList.remove('is-away'), BALL_HOLD);
      ballTimer = setTimeout(runBallCycle, BALL_HOLD + BALL_PAUSE);
    }

    function runLegsCycle() {
      if (!isPosterVisible) return;
      legs.classList.add('is-wiggle');
      setTimeout(() => legs.classList.remove('is-wiggle'), LEGS_HOLD);
      legsTimer = setTimeout(runLegsCycle, LEGS_HOLD + LEGS_PAUSE);
    }

    // Viewport observer to avoid running timers offscreen
    if ('IntersectionObserver' in window) {
      const posterObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            isPosterVisible = entry.isIntersecting;
            if (isPosterVisible) {
              runBallCycle();
              setTimeout(runLegsCycle, LEGS_START_DELAY);
            } else {
              clearTimeout(ballTimer);
              clearTimeout(legsTimer);
              resetPosterEffects();
            }
          });
        },
        { threshold: 0.1 }
      );
      posterObserver.observe(poster);
    } else {
      isPosterVisible = true;
      runBallCycle();
      setTimeout(runLegsCycle, LEGS_START_DELAY);
    }
  }
})();

// -----------------------------------------------------------------------------
// IntersectionObserver Scroll Reveal
// -----------------------------------------------------------------------------

(function initScrollReveal() {
  const revealEls = document.querySelectorAll('.reveal');
  if (!revealEls.length) return;

  if (!('IntersectionObserver' in window)) {
    revealEls.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  revealEls.forEach((el) => observer.observe(el));
})();

// -----------------------------------------------------------------------------
// Copy IBAN Button
// -----------------------------------------------------------------------------

(function initCopyIban() {
  const copyBtn = document.getElementById('btn-copy-iban');
  if (!copyBtn) return;

  copyBtn.addEventListener('click', async () => {
    const ibanValue = 'CH5809000000820006450';
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(ibanValue);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = ibanValue;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }

      const copyTextSpan = copyBtn.querySelector('.btn-copy-text');
      const originalText = copyTextSpan.textContent;
      copyTextSpan.textContent = 'Kopiert! ✓';
      copyBtn.classList.add('is-copied');

      setTimeout(() => {
        copyTextSpan.textContent = originalText;
        copyBtn.classList.remove('is-copied');
      }, 2000);
    } catch (err) {
      console.error('Failed to copy IBAN', err);
    }
  });
})();

// -----------------------------------------------------------------------------
// Live Countdown to 27. September 2026, 10:00
// -----------------------------------------------------------------------------

(function initCountdown() {
  const countdownVal = document.getElementById('countdown-val');
  if (!countdownVal) return;

  // Target: 27. September 2026 at 10:00 AM local time
  const targetDate = new Date('2026-09-27T10:00:00').getTime();

  function updateCountdown() {
    const now = Date.now();
    const diff = targetDate - now;

    if (diff <= 0) {
      countdownVal.textContent = 'Abstimmung läuft!';
      return;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (days > 0) {
      countdownVal.textContent = `Noch ${days}d ${hours}h`;
    } else if (hours > 0) {
      countdownVal.textContent = `Noch ${hours}h ${mins}m`;
    } else {
      countdownVal.textContent = `Noch ${mins} Min.`;
    }
  }

  updateCountdown();
  setInterval(updateCountdown, 30000);
})();
