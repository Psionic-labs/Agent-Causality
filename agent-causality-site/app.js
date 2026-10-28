(function () {
  "use strict";

  var motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReduced() {
    return motionQuery.matches;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }


  function setupVideo() {
    var slot = document.getElementById("video-slot");
    var facade = document.getElementById("video-facade");
    var player = document.getElementById("video-player");
    if (!slot || !facade || !player) return;

    facade.addEventListener("click", function () {
      slot.classList.add("is-playing");
      facade.setAttribute("aria-hidden", "true");
      facade.tabIndex = -1;

      var led = slot.closest(".monitor") &&
        slot.closest(".monitor").querySelector(".bezel-foot .bezel-led");
      if (led) {
        led.classList.add("is-live");
        led.innerHTML = "<i aria-hidden=\"true\"></i> PLAYING";
      }
      var plate = slot.closest(".monitor") &&
        slot.closest(".monitor").querySelector(".bezel-foot .bezel-plate");
      if (plate) plate.textContent = "DEMO REEL / IN-PAGE";

      var attempt = player.play();
      if (attempt && typeof attempt.catch === "function") {
        attempt.catch(function () {
          player.controls = true;
        });
      }
      window.requestAnimationFrame(function () {
        player.focus({ preventScroll: true });
      });
    });

    player.addEventListener("play", function () {
      slot.classList.add("is-playing");
    });
    player.addEventListener("ended", function () {
      var led = slot.closest(".monitor") &&
        slot.closest(".monitor").querySelector(".bezel-foot .bezel-led");
      if (led) led.innerHTML = "<i aria-hidden=\"true\"></i> ENDED";
    });
  }

  function setupTimeline() {
    var scroller = document.getElementById("timeline-scroller");
    if (!scroller) return;

    var steps = scroller.querySelectorAll(".time-step");
    var prev = document.getElementById("timeline-prev");
    var next = document.getElementById("timeline-next");
    var readout = document.getElementById("timeline-readout");
    var fill = document.getElementById("timeline-progress-fill");
    var pending = false;

    function update() {
      pending = false;
      var max = scroller.scrollWidth - scroller.clientWidth;
      var fraction = max > 0 ? scroller.scrollLeft / max : 1;
      var index = clamp(Math.round(fraction * 3), 0, 3);
      if (readout) readout.textContent = "Step " + (index + 1) + " of 4";
      if (fill) fill.style.width = ((index + 1) * 25) + "%";
    }

    function requestUpdate() {
      if (pending) return;
      pending = true;
      window.requestAnimationFrame(update);
    }

    function step(direction) {
      var first = steps[0];
      var distance = first ? first.getBoundingClientRect().width + 15 : scroller.clientWidth * 0.8;
      scroller.scrollBy({
        left: direction * distance,
        behavior: prefersReduced() ? "auto" : "smooth"
      });
    }

    scroller.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    if (prev) prev.addEventListener("click", function () { step(-1); });
    if (next) next.addEventListener("click", function () { step(1); });
    window.requestAnimationFrame(update);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;"
      }[character];
    });
  }

  function setupExplorer() {
    var map = document.getElementById("run-map");
    var nodesLayer = document.getElementById("run-nodes");
    var edgesLayer = document.getElementById("run-edges");
    var inspectorBody = document.getElementById("inspector-body");
    var clearButton = document.getElementById("inspector-clear");
    if (!map || !nodesLayer || !edgesLayer || !inspectorBody) return;

    var events = [
      {
        id: "n0",
        eventId: "EV-001",
        agent: "orchestrator",
        event: "run.start",
        x: 9,
        y: 50,
        parents: [],
        summary: "Dispatches the refund review plan to three parallel agents.",
        inputs: ["task: refund review", "refund_id: RF-1042"],
        provenance: ["user request → orchestrator", "run config: review policy v3"]
      },
      {
        id: "n1",
        eventId: "EV-002",
        agent: "intake",
        event: "tool_result",
        x: 26,
        y: 17,
        parents: ["n0"],
        summary: "Reads the customer record from the CRM and returns eligibility.",
        inputs: ["refund_id: RF-1042"],
        provenance: ["CRM read · customers.customer_status = eligible"]
      },
      {
        id: "n2",
        eventId: "EV-003",
        agent: "risk_checker",
        event: "tool_error → fallback",
        x: 26,
        y: 80,
        parents: ["n0"],
        fault: true,
        summary: "The risk service returned a schema mismatch. The adapter wrote its default score instead of failing the branch.",
        inputs: ["customer_id: C-8821"],
        provenance: ["fallback default · risk_score = 0.2", "expected baseline: 0.8"],
        attribution: "Fallback path in branch risk_checker wrote risk_score = 0.2 after a schema mismatch. That value was consumed by decision.merge."
      },
      {
        id: "n3",
        eventId: "EV-004",
        agent: "policy_lookup",
        event: "tool_result",
        x: 26,
        y: 48,
        parents: ["n0"],
        summary: "Retrieves the current refund policy and its 30-day window.",
        inputs: ["order_id: O-5519"],
        provenance: ["policy service · refund_policy = v3"]
      },
      {
        id: "n4",
        eventId: "EV-005",
        agent: "decision",
        event: "merge_decision",
        x: 48,
        y: 50,
        parents: ["n1", "n2", "n3"],
        summary: "Combines customer status, risk score, and policy into an approval.",
        inputs: ["customer_status = eligible", "risk_score = 0.2", "refund_policy = v3"],
        provenance: ["merge of intake + risk_checker + policy_lookup", "decision contract: manual review below 0.5"]
      },
      {
        id: "n5",
        eventId: "EV-006",
        agent: "refund_writer",
        event: "tool_call",
        x: 68,
        y: 24,
        parents: ["n4"],
        summary: "Issues the refund from the approved decision.",
        inputs: ["decision = approved", "refund_amount = 1240"],
        provenance: ["decision output → payments.issue_refund"]
      },
      {
        id: "n6",
        eventId: "EV-007",
        agent: "audit_gate",
        event: "check.failed",
        x: 86,
        y: 58,
        parents: ["n4", "n5"],
        failure: true,
        summary: "The audit gate flags the refund because the risk score required manual review.",
        inputs: ["decision = approved", "risk_score = 0.2", "contract: review below 0.5"],
        provenance: ["audit policy · review_threshold = 0.5", "reads decision and refund records"]
      },
      {
        id: "n7",
        eventId: "EV-008",
        agent: "ops_alert",
        event: "terminal.failure",
        x: 86,
        y: 84,
        parents: ["n6"],
        failure: true,
        summary: "Pages the on-call engineer. The incident surfaces several events after the fallback.",
        inputs: ["audit = flagged", "severity = high"],
        provenance: ["audit_gate → alerting.pager"]
      }
    ];

    var edges = [
      ["n0", "n1", "gold"],
      ["n0", "n2", "gold"],
      ["n0", "n3", "gold"],
      ["n1", "n4", ""],
      ["n2", "n4", ""],
      ["n3", "n4", ""],
      ["n4", "n5", ""],
      ["n4", "n6", ""],
      ["n5", "n6", "gold"],
      ["n6", "n7", "gold"]
    ];

    var byId = {};
    var nodeButtons = {};
    var edgePaths = [];
    var selectedId = null;
    var emptyHTML = inspectorBody.innerHTML;

    events.forEach(function (event) {
      byId[event.id] = event;
    });

    var SVG_NS = "http://www.w3.org/2000/svg";

    edges.forEach(function (edge) {
      var from = byId[edge[0]];
      var to = byId[edge[1]];
      if (!from || !to) return;
      var midX = from.x + (to.x - from.x) * 0.55;
      var path = document.createElementNS(SVG_NS, "path");
      var d;
      if (Math.abs(to.y - from.y) < 3) {
        d = "M" + from.x + " " + from.y + " L" + to.x + " " + to.y;
      } else {
        d = "M" + from.x + " " + from.y + " C" + midX + " " + from.y + ", " + midX + " " + to.y + ", " + to.x + " " + to.y;
      }
      path.setAttribute("d", d);
      path.setAttribute("class", "edge" + (edge[2] === "gold" ? " edge--gold" : ""));
      path.dataset.from = edge[0];
      path.dataset.to = edge[1];
      edgesLayer.appendChild(path);
      edgePaths.push(path);
    });

    function createNode(event) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "node" + (event.fault ? " node--fault" : "") + (event.failure ? " node--failure" : "");
      button.style.left = event.x + "%";
      button.style.top = event.y + "%";
      button.dataset.id = event.id;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute(
        "aria-label",
        event.agent + ", " + event.event + ". " + event.summary + " Activate to trace its causal chain."
      );

      var marker = document.createElement("span");
      marker.className = "node-marker";
      marker.setAttribute("aria-hidden", "true");

      var agent = document.createElement("span");
      agent.className = "node-agent";
      agent.textContent = event.agent;

      var name = document.createElement("span");
      name.className = "node-event";
      name.textContent = event.event;

      button.appendChild(marker);
      button.appendChild(agent);
      button.appendChild(name);

      if (event.fault) {
        var faultFlag = document.createElement("span");
        faultFlag.className = "node-flag";
        faultFlag.textContent = "FAULT INJECTED";
        button.appendChild(faultFlag);
      } else if (event.failure) {
        var failureFlag = document.createElement("span");
        failureFlag.className = "node-flag node-flag--failure";
        failureFlag.textContent = "FAILURE";
        button.appendChild(failureFlag);
      }

      button.addEventListener("click", function () {
        selectEvent(event.id);
      });

      nodesLayer.appendChild(button);
      nodeButtons[event.id] = button;
    }

    events.forEach(createNode);

    function getAncestors(id) {
      var chain = new Set();
      var stack = [id];
      while (stack.length) {
        var current = stack.pop();
        if (chain.has(current)) continue;
        chain.add(current);
        var event = byId[current];
        if (!event) continue;
        event.parents.forEach(function (parent) {
          if (!chain.has(parent)) stack.push(parent);
        });
      }
      return chain;
    }

    function listMarkup(items, className) {
      return "<ul>" + items.map(function (item) {
        return "<li>" + escapeHtml(item) + "</li>";
      }).join("") + "</ul>";
    }

    function renderInspector(event, chain) {
      var parents;
      if (event.parents.length === 0) {
        parents = "Root decision — no causal parents.";
      } else {
        parents = event.parents.map(function (parentId) {
          var parent = byId[parentId];
          return parent.agent + " (" + parent.eventId + ")";
        }).join(" · ");
      }

      var attribution = "";
      if (event.attribution) {
        attribution =
          '<div class="ins-attribution">' +
            '<span class="ins-attribution-head">ATTRIBUTION</span>' +
            "<p>" + escapeHtml(event.attribution) + "</p>" +
            "<strong>branch " + escapeHtml(event.agent) + " · fallback path</strong>" +
          "</div>";
      }

      inspectorBody.innerHTML =
        '<p class="ins-kicker">' + escapeHtml(event.eventId) + " / BRANCH " + escapeHtml(event.agent) + "</p>" +
        '<h3 class="ins-event">' + escapeHtml(event.event) + "</h3>" +
        '<p class="ins-agent">agent · ' + escapeHtml(event.agent) + "</p>" +
        '<p class="ins-summary">' + escapeHtml(event.summary) + "</p>" +
        '<div class="ins-section"><h4>Inputs</h4>' + listMarkup(event.inputs) + "</div>" +
        '<div class="ins-section"><h4>Provenance</h4>' + listMarkup(event.provenance) + "</div>" +
        '<div class="ins-section"><h4>Causal parents</h4><p class="ins-parents">' + escapeHtml(parents) + "</p></div>" +
        attribution +
        '<div class="ins-chain">CHAIN ' + chain.size + " / " + events.length + " EVENTS · ROOT → " + escapeHtml(event.agent) + "</div>";
    }

    function resetInspector() {
      inspectorBody.innerHTML = emptyHTML;
      if (clearButton) clearButton.hidden = true;
    }

    function selectEvent(id) {
      var event = byId[id];
      if (!event) return;
      selectedId = id;
      var chain = getAncestors(id);

      events.forEach(function (item) {
        var button = nodeButtons[item.id];
        if (!button) return;
        var inChain = chain.has(item.id);
        var selected = item.id === id;
        button.classList.toggle("is-selected", selected);
        button.classList.toggle("is-cause", inChain && !selected);
        button.classList.toggle("is-dim", !inChain && !selected);
        button.setAttribute("aria-pressed", selected ? "true" : "false");
      });

      edgePaths.forEach(function (path) {
        var inChain = chain.has(path.dataset.from) && chain.has(path.dataset.to);
        path.classList.toggle("is-cause", inChain);
        path.classList.toggle("is-dim", !inChain);
      });

      renderInspector(event, chain);
      if (clearButton) clearButton.hidden = false;
      inspectorBody.scrollTop = 0;
    }

    function clearSelection(focusPrevious) {
      var previous = selectedId ? nodeButtons[selectedId] : null;
      selectedId = null;
      events.forEach(function (event) {
        var button = nodeButtons[event.id];
        if (!button) return;
        button.classList.remove("is-selected", "is-cause", "is-dim");
        button.setAttribute("aria-pressed", "false");
      });
      edgePaths.forEach(function (path) {
        path.classList.remove("is-cause", "is-dim");
      });
      resetInspector();
      if (focusPrevious && previous) previous.focus();
    }

    if (clearButton) {
      clearButton.addEventListener("click", function () {
        clearSelection(true);
      });
    }

    map.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && selectedId) {
        clearSelection(true);
      }
    });
  }

  function setupCopy() {
    var button = document.getElementById("copy-btn");
    var codeBlock = document.getElementById("quickstart-code");
    var status = document.getElementById("copy-status");
    if (!button || !codeBlock) return;

    var commands = Array.prototype.map.call(codeBlock.querySelectorAll(".cmd"), function (command) {
      return command.textContent.trim();
    }).join("\n");
    var resetTimer = null;

    function legacyCopy(text) {
      var textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.top = "-100px";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);
      var ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (error) {
        ok = false;
      }
      textarea.remove();
      return ok;
    }

    function showResult(message, copied) {
      if (status) status.textContent = message;
      if (resetTimer) window.clearTimeout(resetTimer);
      if (copied) {
        button.textContent = "Copied";
        button.classList.add("is-copied");
      }
      resetTimer = window.setTimeout(function () {
        button.textContent = "Copy";
        button.classList.remove("is-copied");
        if (status) status.textContent = "";
      }, 2400);
    }

    button.addEventListener("click", function () {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(commands).then(function () {
          showResult("Commands copied to clipboard.", true);
        }).catch(function () {
          if (legacyCopy(commands)) {
            showResult("Commands copied to clipboard.", true);
          } else {
            showResult("Copy failed. Select the commands manually.", false);
          }
        });
      } else if (legacyCopy(commands)) {
        showResult("Commands copied to clipboard.", true);
      } else {
        showResult("Copy failed. Select the commands manually.", false);
      }
    });
  }

  function setupReveal() {
    var selector = [
      ".section-head", ".problem-copy", ".trace-figure",
      ".instruments > .instrument", ".time-step",
      ".explorer", ".moments > .moment",
      ".quickstart-copy", ".terminal", ".video-figure"
    ].join(", ");
    var els = Array.prototype.slice.call(document.querySelectorAll(selector));
    if (!els.length) return;

    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || typeof IntersectionObserver === "undefined") {
      for (var i = 0; i < els.length; i += 1) els[i].classList.add("reveal", "is-in");
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i += 1) {
        var entry = entries[i];
        if (!entry.isIntersecting) continue;
        var el = entry.target;
        var parent = el.parentElement;
        var kin = parent
          ? Array.prototype.filter.call(parent.children, function (child) {
              return child.classList && child.classList.contains("reveal");
            })
          : [el];
        var index = kin.indexOf(el);
        if (index < 0) index = 0;
        el.style.transitionDelay = String(Math.min(index, 3) * 70) + "ms";
        el.classList.add("is-in");
        observer.unobserve(el);
      }
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.15 });

    for (var j = 0; j < els.length; j += 1) {
      els[j].classList.add("reveal");
      observer.observe(els[j]);
    }
  }

  setupVideo();
  setupTimeline();
  setupExplorer();
  setupCopy();
  setupReveal();
})();
