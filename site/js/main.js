// Always land on the hero graphic, even if the URL has a #hash or the
// browser would otherwise restore a previous scroll position.
if ('scrollRestoration' in history) {
  history.scrollRestoration = 'manual';
}

function scrollToTop() {
  window.scrollTo(0, 0);
}

// Drop any #hash right away so the browser can't (re-)apply its own
// anchor scroll once images further down have finished loading.
if (location.hash) {
  history.replaceState(null, '', location.pathname + location.search);
}

scrollToTop();
document.addEventListener('DOMContentLoaded', scrollToTop);
window.addEventListener('load', scrollToTop);
// Images loading after `load` can still shift layout; do one more pass.
window.setTimeout(scrollToTop, 300);


// Interactive poster behaviour: elements react when the pointer gets close.
//
// The poster is built from individually positioned SVGs (see .el classes in
// css/styles.css). Positions/sizes below are given as fractions of the
// poster's own width/height, matching the CSS percentages, so the hit-test
// stays correct at any poster size.

(function () {
  var poster = document.getElementById('poster');
  var ball = document.getElementById('ball');
  var legs = document.getElementById('woman-legs');

  if (!poster || !ball || !legs) return;

  // Ball's resting spot (in the man's hands), as fractions of the poster box.
  var BALL_REST = { x: 0.788427 + 0.071854 / 2, y: 0.352381 + 0.050904 / 2 };

  // How close (in % of poster width) the pointer needs to get to trigger
  // each effect.
  var BALL_RADIUS = 0.14;
  var LEGS_RADIUS = 0.16;

  function distance(ax, ay, bx, by) {
    var dx = ax - bx;
    var dy = ay - by;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function handlePointer(clientX, clientY) {
    var rect = poster.getBoundingClientRect();
    if (rect.width === 0) return;

    // Pointer position as a fraction of the poster box.
    var px = (clientX - rect.left) / rect.width;
    var py = (clientY - rect.top) / rect.height;

    // Ball: fly to the woman's hands when the pointer nears its rest spot.
    var ballDist = distance(px, py, BALL_REST.x, BALL_REST.y);
    ball.classList.toggle('is-away', ballDist < BALL_RADIUS);

    // Legs: turn a little when the pointer nears them.
    var legsRect = legs.getBoundingClientRect();
    var legsCx = (legsRect.left + legsRect.width / 2 - rect.left) / rect.width;
    var legsCy = (legsRect.top + legsRect.height / 2 - rect.top) / rect.height;
    var legsDist = distance(px, py, legsCx, legsCy);
    legs.classList.toggle('is-wiggle', legsDist < LEGS_RADIUS);
  }

  function reset() {
    ball.classList.remove('is-away');
    legs.classList.remove('is-wiggle');
  }

  poster.addEventListener('pointermove', function (event) {
    handlePointer(event.clientX, event.clientY);
  });

  poster.addEventListener('pointerleave', reset);
})();

// Fade sections in as they scroll into view.
(function () {
  var revealEls = document.querySelectorAll('.reveal');
  if (!revealEls.length) return;

  if (!('IntersectionObserver' in window)) {
    revealEls.forEach(function (el) { el.classList.add('is-visible'); });
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  revealEls.forEach(function (el) { observer.observe(el); });
})();

