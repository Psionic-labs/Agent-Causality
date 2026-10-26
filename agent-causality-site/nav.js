(function () {
  "use strict";

  var html = document.documentElement;
  var button = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  var label = button ? button.querySelector(".nav-toggle-label") : null;
  if (!button || !nav || !label) return;

  function fromEvent(target) {
    if (target instanceof Element) return target;
    if (target && target.parentElement) return target.parentElement;
    return null;
  }

  function isNarrow() {
    return window.getComputedStyle(button).display !== "none";
  }

  function setNav(mode, restoreFocus) {
    if (mode !== "open" && mode !== "closed") return;
    var open = mode === "open";
    var narrow = isNarrow();
    var expanded = open ? "true" : "false";
    var hidden = narrow && !open;
    var word = open ? "Close" : "Menu";
    var same =
      html.getAttribute("data-nav") === mode &&
      button.getAttribute("aria-expanded") === expanded &&
      label.textContent === word &&
      (hidden ? nav.getAttribute("aria-hidden") === "true" : !nav.hasAttribute("aria-hidden"));
    if (same) return;
    html.setAttribute("data-nav", mode);
    button.setAttribute("aria-expanded", expanded);
    label.textContent = word;
    if (hidden) nav.setAttribute("aria-hidden", "true");
    else nav.removeAttribute("aria-hidden");
    if (!open && restoreFocus !== false && nav.contains(document.activeElement)) {
      button.focus();
    }
  }

  button.addEventListener("click", function () {
    setNav(html.getAttribute("data-nav") === "open" ? "closed" : "open");
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      setNav("closed");
      return;
    }
    if (event.key !== "Tab" || html.getAttribute("data-nav") !== "open" || !isNarrow()) return;
    var links = nav.querySelectorAll("a");
    var last = links.length ? links[links.length - 1] : button;
    if (event.shiftKey && document.activeElement === button) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      button.focus();
    }
  });

  nav.addEventListener("click", function (event) {
    var element = fromEvent(event.target);
    if (!element || !element.closest("a")) return;
    setNav("closed", false);
  });

  document.addEventListener("click", function (event) {
    if (html.getAttribute("data-nav") !== "open") return;
    var element = fromEvent(event.target);
    if (element && element.closest(".site-header")) return;
    setNav("closed");
  });

  window.addEventListener("resize", function () {
    if (!isNarrow()) setNav("closed");
  });

  setNav(isNarrow() && html.getAttribute("data-nav") === "open" ? "open" : "closed");
})();
