(function () {
  "use strict";

  var motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

  function prefersReduced() {
    return motionQuery.matches;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function easeOutCubic(value) {
    return 1 - Math.pow(1 - value, 3);
  }

  function drawMonitor() {
    var canvas = document.getElementById("hero-canvas");
    if (!canvas) return;

    var ctx = canvas.getContext("2d");
    if (!ctx) return;

    var screen = canvas.parentElement;
    var eventsEl = document.getElementById("events-readout");
    var alertEl = document.getElementById("branch-alert");
    var alertTextEl = document.getElementById("branch-alert-text");
    var logRowsEl = document.getElementById("log-rows");

    var width = 0;
    var height = 0;
    var dpr = 1;
    var isMobile = false;
    var rafId = null;
    var running = false;
    var visible = true;
    var elapsed = 0;
    var origin = 0;
    var lastHudAt = 0;
    var alertState = "";

    var TOP_THRESHOLD = 0.26;
    var BOTTOM_THRESHOLD = 0.76;
    var GROW = 2;
    var HOLD = 2.6;
    var FADE = 0.9;
    var CYCLE = 7.4;

    var branches = [
      { t: 0.12, dx: 0.15, ty: 0.36, offset: 0.3, mobile: true },
      { t: 0.23, dx: 0.13, ty: 0.64, offset: 2.8 },
      { t: 0.34, dx: 0.16, ty: 0.39, offset: 1.1, mobile: true },
      { t: 0.45, dx: 0.15, ty: 0.93, offset: 4.8, cross: true, mobile: true },
      { t: 0.56, dx: 0.17, ty: 0.34, offset: 3.4 },
      { t: 0.68, dx: 0.14, ty: 0.67, offset: 0.9 },
      { t: 0.8, dx: 0.15, ty: 0.4, offset: 5.6, mobile: true },
      { t: 0.9, dx: 0.09, ty: 0.62, offset: 2 }
    ];

    var trunkNodePositions = [0.08, 0.2, 0.31, 0.43, 0.55, 0.67, 0.79, 0.91];

    var LOG_EVENTS = [
      { id: "ev-001", time: "t+00.00", node: "orchestrator", kind: "run.start" },
      { id: "ev-002", time: "t+00.41", node: "intake", kind: "tool_result" },
      { id: "ev-003", time: "t+00.83", node: "risk_checker", kind: "tool_error → fallback", cls: "is-fault" },
      { id: "ev-004", time: "t+01.22", node: "policy_lookup", kind: "tool_result" },
      { id: "ev-005", time: "t+01.64", node: "decision", kind: "merge_decision" },
      { id: "ev-006", time: "t+02.05", node: "refund_writer", kind: "tool_call" },
      { id: "ev-007", time: "t+02.47", node: "audit_gate", kind: "check.failed", cls: "is-terminal" },
      { id: "ev-008", time: "t+02.88", node: "ops_alert", kind: "terminal.failure", cls: "is-terminal" }
    ];
    var LOG_VISIBLE = 6;
    var LOG_INTERVAL = 0.92;
    var logIndex = 0;
    var lastLogAt = 0;
    var logMode = "";

    function pushLogRow(flash) {
      if (!logRowsEl) return;
      var ev = LOG_EVENTS[logIndex % LOG_EVENTS.length];
      logIndex += 1;
      var row = document.createElement("div");
      row.className = "log-row" + (ev.cls ? " " + ev.cls : "") + (flash ? " is-new" : "");
      var cells = [ev.id, ev.time, ev.node, ev.kind];
      for (var i = 0; i < cells.length; i += 1) {
        var cell = document.createElement("span");
        cell.textContent = cells[i];
        row.appendChild(cell);
      }
      var prev = logRowsEl.querySelector(".is-new");
      if (prev) prev.classList.remove("is-new");
      logRowsEl.appendChild(row);
      while (logRowsEl.children.length > LOG_VISIBLE) {
        logRowsEl.removeChild(logRowsEl.firstChild);
      }
    }

    function updateLog(time) {
      if (!logRowsEl) return;
      if (logMode !== "live") {
        logMode = "live";
        logIndex = 0;
        logRowsEl.textContent = "";
        for (var i = 0; i < LOG_VISIBLE; i += 1) pushLogRow(false);
        lastLogAt = time;
        return;
      }
      if (time - lastLogAt < LOG_INTERVAL) return;
      lastLogAt = time;
      pushLogRow(true);
    }

    function setAlert(state) {
      if (state === alertState || !alertEl || !alertTextEl) return;
      alertState = state;
      alertEl.classList.toggle("is-pruned", state === "pruned");
      alertTextEl.textContent = state === "pruned"
        ? "Branch pruned · B-04"
        : "Branch detected · B-04";
    }

    function resizeCanvas() {
      var rect = screen.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return false;
      isMobile = window.matchMedia("(max-width: 640px)").matches;
      dpr = Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2);
      width = Math.round(rect.width);
      height = Math.round(rect.height);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return true;
    }

    function trunkPoint(t) {
      return {
        x: -0.04 + t * 1.08,
        y: 0.5 + Math.sin(t * Math.PI * 2.1 + 0.6) * 0.018 - (t - 0.5) * 0.035
      };
    }

    function buildTrunk() {
      var points = [];
      for (var i = 0; i <= 120; i += 1) {
        points.push(trunkPoint(i / 120));
      }
      return points;
    }

    function buildBranch(def) {
      var start = trunkPoint(def.t);
      var endX = clamp(start.x + def.dx, 0.02, 1.02);
      var endY = def.ty;
      var cp1x = start.x + (endX - start.x) * 0.24;
      var cp1y = start.y + (endY - start.y) * 0.06;
      var cp2x = start.x + (endX - start.x) * 0.64;
      var cp2y = endY - (endY - start.y) * 0.12;
      var points = [];
      var i;
      for (i = 0; i <= 44; i += 1) {
        var t = i / 44;
        var mt = 1 - t;
        points.push({
          x: mt * mt * mt * start.x + 3 * mt * mt * t * cp1x + 3 * mt * t * t * cp2x + t * t * t * endX,
          y: mt * mt * mt * start.y + 3 * mt * mt * t * cp1y + 3 * mt * t * t * cp2y + t * t * t * endY
        });
      }
      var crossIdx = null;
      if (def.cross) {
        var threshold = def.ty < 0.5 ? TOP_THRESHOLD : BOTTOM_THRESHOLD;
        for (i = 1; i < points.length; i += 1) {
          if (def.ty < 0.5 ? points[i].y <= threshold : points[i].y >= threshold) {
            crossIdx = i;
            break;
          }
        }
      }
      return { points: points, crossIdx: crossIdx };
    }

    function branchState(def, time) {
      var local = (time + def.offset) % CYCLE;
      var progress = 0;
      var alpha = 0;
      if (local < GROW) {
        progress = easeOutCubic(local / GROW);
        alpha = 1;
      } else if (local < GROW + HOLD) {
        progress = 1;
        alpha = 1;
      } else if (local < GROW + HOLD + FADE) {
        progress = 1;
        alpha = 1 - (local - GROW - HOLD) / FADE;
      }
      return { progress: progress, alpha: alpha };
    }

    function strokePolyline(points, color, lineWidth) {
      if (points.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(points[0].x * width, points[0].y * height);
      for (var i = 1; i < points.length; i += 1) {
        ctx.lineTo(points[i].x * width, points[i].y * height);
      }
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }

    function traceSegment(points, from, to) {
      ctx.beginPath();
      ctx.moveTo(points[from].x * width, points[from].y * height);
      for (var i = from + 1; i <= to; i += 1) {
        ctx.lineTo(points[i].x * width, points[i].y * height);
      }
    }

    function drawBackground() {
      var base = ctx.createLinearGradient(0, 0, 0, height);
      base.addColorStop(0, "#221009");
      base.addColorStop(0.55, "#170a06");
      base.addColorStop(1, "#0b0402");
      ctx.fillStyle = base;
      ctx.fillRect(0, 0, width, height);

      var glow = ctx.createRadialGradient(
        width * 0.5, height * 0.5, 0,
        width * 0.5, height * 0.5, Math.max(width, height) * 0.64
      );
      glow.addColorStop(0, "rgba(255, 104, 48, 0.065)");
      glow.addColorStop(0.65, "rgba(255, 104, 48, 0.02)");
      glow.addColorStop(1, "rgba(255, 104, 48, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(0, 0, width, height);

      var band = ctx.createLinearGradient(0, 0, 0, height * 0.24);
      band.addColorStop(0, "rgba(168, 34, 22, 0.2)");
      band.addColorStop(1, "rgba(168, 34, 22, 0)");
      ctx.fillStyle = band;
      ctx.fillRect(0, 0, width, height * 0.24);
    }

    function drawThresholds() {
      var levels = [TOP_THRESHOLD, BOTTOM_THRESHOLD];
      for (var i = 0; i < levels.length; i += 1) {
        var y = levels[i] * height;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.strokeStyle = "rgba(255, 92, 38, 0.07)";
        ctx.lineWidth = 6;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.strokeStyle = "rgba(255, 92, 38, 0.38)";
        ctx.lineWidth = 1;
        ctx.stroke();

        for (var x = 0.08; x < 1; x += 0.115) {
          ctx.beginPath();
          ctx.moveTo(x * width, y - 2);
          ctx.lineTo(x * width, y + 2);
          ctx.strokeStyle = "rgba(255, 92, 38, 0.42)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }

    function drawRegistration() {
      var pad = Math.max(9, width * 0.018);
      var size = Math.max(7, width * 0.012);
      ctx.strokeStyle = "rgba(240, 166, 60, 0.2)";
      ctx.lineWidth = 1;
      var corners = [
        [pad, pad, 1, 1],
        [width - pad, pad, -1, 1],
        [pad, height - pad, 1, -1],
        [width - pad, height - pad, -1, -1]
      ];
      for (var i = 0; i < corners.length; i += 1) {
        var c = corners[i];
        ctx.beginPath();
        ctx.moveTo(c[0], c[1] + c[3] * size);
        ctx.lineTo(c[0], c[1]);
        ctx.lineTo(c[0] + c[2] * size, c[1]);
        ctx.stroke();
      }
    }

    function drawTrunk() {
      var points = buildTrunk();
      if (!isMobile) {
        strokePolyline(points, "rgba(245, 238, 218, 0.035)", 12);
        strokePolyline(points, "rgba(245, 238, 218, 0.075)", 5.5);
      }
      strokePolyline(points, "rgba(245, 238, 218, 0.25)", 2.6);
      strokePolyline(points, "rgba(245, 238, 218, 0.92)", 1.25);
    }

    function drawGoldNode(x, y, size, alpha) {
      var glow = ctx.createRadialGradient(x, y, 0, x, y, size * 4);
      glow.addColorStop(0, "rgba(255, 211, 95, " + (0.2 * alpha) + ")");
      glow.addColorStop(1, "rgba(255, 211, 95, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - size * 4, y - size * 4, size * 8, size * 8);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = "#ffd35f";
      ctx.fillRect(x - size / 2, y - size / 2, size, size);
      ctx.globalAlpha = 1;
    }

    function drawRedNode(x, y, size, alpha) {
      var glow = ctx.createRadialGradient(x, y, 0, x, y, size * 4.5);
      glow.addColorStop(0, "rgba(239, 65, 48, " + (0.24 * alpha) + ")");
      glow.addColorStop(1, "rgba(239, 65, 48, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - size * 4.5, y - size * 4.5, size * 9, size * 9);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = "#ef4130";
      ctx.fillRect(x - size / 2, y - size / 2, size, size);
      ctx.globalAlpha = 1;
    }

    function drawFray(point, alpha) {
      var x = point.x * width;
      var y = point.y * height;
      var spreads = [
        [5, -4],
        [7, 2],
        [2, 6]
      ];
      ctx.strokeStyle = "rgba(239, 65, 48, " + (0.75 * alpha) + ")";
      ctx.lineWidth = 1;
      for (var i = 0; i < spreads.length; i += 1) {
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + spreads[i][0], y + spreads[i][1]);
        ctx.stroke();
      }
    }

    function drawBranch(def, state, staticMode) {
      if (state.alpha <= 0.01) return false;
      var geometry = buildBranch(def);
      var points = geometry.points;
      var last = points.length - 1;
      var maxIndex = clamp(Math.round(state.progress * last), 1, last);
      var pruned = false;

      if (def.cross && geometry.crossIdx !== null) {
        var crossIdx = geometry.crossIdx;
        if (maxIndex <= crossIdx) {
          traceSegment(points, 0, maxIndex);
          if (!isMobile) {
            ctx.strokeStyle = "rgba(217, 168, 71, " + (0.1 * state.alpha) + ")";
            ctx.lineWidth = 4;
            ctx.stroke();
          }
          ctx.strokeStyle = "rgba(217, 168, 71, " + (0.82 * state.alpha) + ")";
          ctx.lineWidth = 1;
          ctx.stroke();
        } else {
          traceSegment(points, 0, crossIdx);
          if (!isMobile) {
            ctx.strokeStyle = "rgba(217, 168, 71, " + (0.1 * state.alpha) + ")";
            ctx.lineWidth = 4;
            ctx.stroke();
          }
          ctx.strokeStyle = "rgba(217, 168, 71, " + (0.9 * state.alpha) + ")";
          ctx.lineWidth = 1;
          ctx.stroke();

          var cutIndex = Math.min(last, crossIdx + Math.max(2, Math.round(last * 0.055)));
          traceSegment(points, crossIdx, cutIndex);
          if (!isMobile) {
            ctx.strokeStyle = "rgba(239, 65, 48, " + (0.17 * state.alpha) + ")";
            ctx.lineWidth = 5;
            ctx.stroke();
          }
          ctx.strokeStyle = "rgba(239, 65, 48, " + state.alpha + ")";
          ctx.lineWidth = 1.2;
          ctx.stroke();

          drawFray(points[cutIndex], state.alpha);
          drawRedNode(points[cutIndex].x * width, points[cutIndex].y * height, isMobile ? 5 : 6, state.alpha);
          pruned = true;
        }
      } else {
        traceSegment(points, 0, maxIndex);
        if (!isMobile) {
          ctx.strokeStyle = "rgba(217, 168, 71, " + (0.09 * state.alpha) + ")";
          ctx.lineWidth = 4;
          ctx.stroke();
        }
        ctx.strokeStyle = "rgba(217, 168, 71, " + (0.78 * state.alpha) + ")";
        ctx.lineWidth = 0.95;
        ctx.stroke();

        if (state.progress > 0.74) {
          var tip = points[maxIndex];
          drawGoldNode(tip.x * width, tip.y * height, isMobile ? 3 : 3.5, state.alpha * (0.45 + state.progress * 0.45));
        }
      }

      if (def.cross && staticMode) pruned = true;
      return pruned;
    }

    function drawTrunkNodes(time) {
      for (var i = 0; i < trunkNodePositions.length; i += 1) {
        var point = trunkPoint(trunkNodePositions[i]);
        var pulse = 0.68 + 0.32 * Math.sin(time * 1.9 + i * 1.7);
        drawGoldNode(point.x * width, point.y * height, isMobile ? 2.8 : 3.4, pulse);
      }
    }

    function drawPulse(time) {
      var point = trunkPoint((time * 0.055) % 1);
      var x = point.x * width;
      var y = point.y * height;
      var radius = isMobile ? 12 : 20;
      var glow = ctx.createRadialGradient(x, y, 0, x, y, radius);
      glow.addColorStop(0, "rgba(255, 247, 228, 0.3)");
      glow.addColorStop(0.35, "rgba(255, 230, 185, 0.08)");
      glow.addColorStop(1, "rgba(255, 230, 185, 0)");
      ctx.fillStyle = glow;
      ctx.fillRect(x - radius, y - radius, radius * 2, radius * 2);
      ctx.fillStyle = "rgba(255, 249, 234, 0.85)";
      ctx.fillRect(x - 1.5, y - 1.5, 3, 3);
    }

    function updateHud(time, now) {
      if (now - lastHudAt < 420) return;
      lastHudAt = now;
      if (eventsEl) {
        var events = Math.round(184 + Math.sin(time * 0.7) * 2 + Math.sin(time * 2.3) * 1.2);
        eventsEl.textContent = String(events);
      }
    }

    function drawFrame(time) {
      drawBackground();
      drawThresholds();
      drawRegistration();

      var list = isMobile ? branches.filter(function (branch) { return branch.mobile; }) : branches;
      var crossing = branches[3];
      var crossState = branchState(crossing, time);
      var crossGeometry = crossing.cross ? buildBranch(crossing) : null;
      var crossAt = crossGeometry && crossGeometry.crossIdx !== null
        ? crossGeometry.crossIdx / (crossGeometry.points.length - 1)
        : 1;
      var pruning = crossState.alpha > 0.02 && crossState.progress >= crossAt;

      for (var i = 0; i < list.length; i += 1) {
        drawBranch(list[i], branchState(list[i], time), false);
      }

      drawTrunk();
      drawTrunkNodes(time);
      drawPulse(time);
      setAlert(pruning ? "pruned" : "detected");
      updateHud(time, performance.now());
      updateLog(time);
    }

    function frame(now) {
      if (!running) return;
      var time = (now - origin) / 1000;
      elapsed = time;
      drawFrame(time);
      rafId = window.requestAnimationFrame(frame);
    }

    function startLoop() {
      if (running) return;
      running = true;
      origin = performance.now() - elapsed * 1000;
      rafId = window.requestAnimationFrame(frame);
    }

    function stopLoop() {
      running = false;
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    function syncLoop() {
      if (visible && !document.hidden) {
        startLoop();
      } else {
        stopLoop();
      }
    }

    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(function () {
        resizeCanvas();
      }).observe(screen);
    } else {
      window.addEventListener("resize", function () {
        resizeCanvas();
      });
    }

    if (typeof IntersectionObserver !== "undefined") {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        syncLoop();
      }, { threshold: 0.04 }).observe(canvas);
    }

    document.addEventListener("visibilitychange", syncLoop);

    resizeCanvas();
    startLoop();
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
      "#hero-title", ".hero-sub", ".hero-actions", ".hero-meta", ".hero-visual",
      ".section-head", ".problem-copy", ".trace-figure",
      ".instruments > .instrument", ".timeline-head", ".time-step",
      ".explorer", ".moments > .moment",
      ".quickstart-copy", ".terminal", ".quickstart-extra", ".footer-top"
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

  drawMonitor();
  setupVideo();
  setupTimeline();
  setupExplorer();
  setupCopy();
  setupReveal();
})();
