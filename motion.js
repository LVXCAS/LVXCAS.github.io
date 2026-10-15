/* lvxcas.github.io motion layer.
 *
 * Everything this animates is already in its final state in the HTML. With
 * JavaScript off, or prefers-reduced-motion set, nothing is hidden and nothing
 * moves: the numbers are the numbers and the struck text is struck.
 *
 *   [data-r]        gets .in when it scrolls into view (CSS does the transition)
 *   [data-line]     same, without the fade: the notebook rail is ruled on entry
 *   [data-stagger]  children get an increasing --d delay
 *   .count, .rail b counts up from zero to the number it already shows
 */
(function () {
  "use strict";
  window.__motion = true;

  var root = document.documentElement;
  var COUNT_MS = 1400;
  var STAGGER_MS = 80;
  var BATCH_STAGGER_MS = 70;
  var STRIKE_DELAY_MS = 450;
  var STRIKE_STEP_MS = 380;

  setupThemeToggle();

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!root.classList.contains("js")) return;          // head fallback already gave up
  if (reduce || !("IntersectionObserver" in window)) {
    root.classList.remove("js");
    return;
  }

  each("[data-stagger]", function (group) {
    Array.prototype.forEach.call(group.children, function (child, i) {
      child.style.setProperty("--d", i * STAGGER_MS + "ms");
    });
  });
  each(".row", function (row) {
    row.querySelectorAll("del").forEach(function (d, i) {
      d.style.setProperty("--d", STRIKE_DELAY_MS + i * STRIKE_STEP_MS + "ms");
    });
  });

  var reveal = new IntersectionObserver(function (entries) {
    var k = 0;
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      reveal.unobserve(e.target);
      e.target.style.setProperty("--b", k++ * BATCH_STAGGER_MS + "ms");
      e.target.classList.add("in");
    });
  }, { rootMargin: "0px 0px -10% 0px", threshold: 0.01 });
  each("[data-r], [data-line]", function (el) { reveal.observe(el); });

  var counters = [];
  each(".count, .rail b", function (el) {
    var c = parseCounter(el);
    if (c) counters.push(c);
  });
  var counting = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      counting.unobserve(e.target);
      run(e.target.__counter);
    });
  }, { threshold: 0.6 });
  counters.forEach(function (c) {
    c.el.__counter = c;
    c.el.textContent = c.render(0);
    counting.observe(c.el);
  });

  // ------------------------------------------------------------ helpers

  function each(sel, fn) { document.querySelectorAll(sel).forEach(fn); }

  function parseCounter(el) {
    var m = el.textContent.match(/^(\D*?)(\d[\d,]*(?:\.\d+)?)(.*)$/);
    if (!m) return null;
    var raw = m[2];
    var value = parseFloat(raw.replace(/,/g, ""));
    if (!value) return null;                             // nothing to count to
    var decimals = (raw.split(".")[1] || "").length;
    var grouped = raw.indexOf(",") !== -1;
    var final = el.textContent;
    el.classList.add("counting");
    el.style.minWidth = final.length + "ch";
    return {
      el: el, value: value, final: final,
      render: function (v) {
        var s = v.toFixed(decimals);
        if (grouped) s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        return m[1] + s + m[3];
      }
    };
  }

  function run(c) {
    var start = null;
    function frame(t) {
      if (start === null) start = t;
      var p = Math.min(1, (t - start) / COUNT_MS);
      var eased = p === 1 ? 1 : 1 - Math.pow(2, -10 * p);
      c.el.textContent = p === 1 ? c.final : c.render(c.value * eased);
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function setupThemeToggle() {
    var btn = document.querySelector(".theme");
    if (!btn) return;
    var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
    function current() {
      return root.getAttribute("data-theme") || (darkQuery.matches ? "dark" : "light");
    }
    function label() {
      var next = current() === "dark" ? "light" : "dark";
      btn.setAttribute("aria-label", "Switch to " + next + " theme");
      btn.title = "Switch to " + next + " theme";
    }
    btn.hidden = false;
    label();
    btn.addEventListener("click", function () {
      var next = current() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) { /* private mode: theme just won't persist */ }
      label();
    });
    if (darkQuery.addEventListener) darkQuery.addEventListener("change", label);
  }
})();
