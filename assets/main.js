// Hero: still, clear, shallow water in the sun. Light ripples across a sandy
// bottom, a few fish and one sea turtle pass slowly above the text, and the
// fish move aside for the cursor. Nothing else.
(function () {
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Work and To try: filter by topic, and reveal the items past the first few. Each section keeps its own state.
  document.querySelectorAll("section").forEach(function (sec) {
    if (!sec.querySelector("[data-topics]")) return;
    var chips = sec.querySelectorAll(".chip"), moreBtn = sec.querySelector("[data-more]"), expanded = false, topic = "";
    function applyFilter() {
      sec.querySelectorAll("[data-topics]").forEach(function (el) {
        var match = !topic || el.getAttribute("data-topics").split("|").indexOf(topic) >= 0;
        el.hidden = !match || (!topic && !expanded && el.classList.contains("extra"));
      });
      if (moreBtn) moreBtn.hidden = expanded || !!topic;
    }
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        topic = c.getAttribute("data-topic");
        chips.forEach(function (o) { o.setAttribute("aria-pressed", o === c ? "true" : "false"); });
        applyFilter();
      });
    });
    if (moreBtn) moreBtn.addEventListener("click", function () { expanded = true; applyFilter(); });
    applyFilter();
  });

  // Search: Ctrl+K or the nav button. The index is fetched the first time it opens.
  var dlg = document.querySelector("dialog.search");
  if (dlg && dlg.showModal) {
    var input = dlg.querySelector("input"), list = dlg.querySelector(".results"), entries = null, on = 0;
    var esc = function (x) { return String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); };
    var render = function () {
      var words = input.value.toLowerCase().split(/\s+/).filter(Boolean);
      var hits = (entries || []).filter(function (e) {
        var hay = (e.t + " " + e.d + " " + e.k).toLowerCase();
        return words.every(function (w) { return hay.indexOf(w) >= 0; });
      }).slice(0, 8);
      on = Math.min(on, Math.max(0, hits.length - 1));
      list.innerHTML = hits.map(function (e, i) {
        var ext = /^http/.test(e.u) ? ' target="_blank" rel="noopener"' : "";
        return '<li><a href="' + esc(e.u) + '"' + ext + (i === on ? ' class="on"' : "") + '><span class="kind">' + esc(e.k) + "</span>" + esc(e.t) + '<span class="desc">' + esc(e.d) + "</span></a></li>";
      }).join("");
    };
    var open = function () {
      if (dlg.open) return;
      dlg.showModal(); input.value = ""; on = 0; render();
      if (!entries) fetch(document.body.getAttribute("data-search")).then(function (r) { return r.json(); }).then(function (d) { entries = d; render(); }).catch(function () { entries = []; });
    };
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
    });
    document.querySelectorAll("[data-search-open]").forEach(function (b) { b.addEventListener("click", open); });
    input.addEventListener("input", function () { on = 0; render(); });
    input.addEventListener("keydown", function (e) {
      var n = list.children.length;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (n) { on = (on + (e.key === "ArrowDown" ? 1 : n - 1)) % n; render(); } }
      else if (e.key === "Enter") { var a = list.querySelector("a.on"); if (a) { dlg.close(); a.click(); } }
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close(); });
    list.addEventListener("click", function (e) { if (e.target.closest("a")) dlg.close(); });
  }

  var canvas = document.getElementById("water");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var hero = canvas.parentElement;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SHADOW = "rgba(23,63,77,0.10)";
  var W = 0, H = 0, time = 0, last = 0, mouse = null, caustics = null, schools = [], turtle = null, giant = null, seen = false, running = false, visible = true;

  function rnd(i) { var x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }

  // Tileable caustic texture: bright Voronoi cell edges, like sunlight on a sandy bottom.
  function makeCaustics() {
    var S = 256, n = 20, pts = [], c = document.createElement("canvas");
    c.width = c.height = S;
    var g = c.getContext("2d"), img = g.createImageData(S, S), i, x, y;
    for (i = 0; i < n; i++) pts.push([rnd(i + 1) * S, rnd(i + 50) * S]);
    for (y = 0; y < S; y++) for (x = 0; x < S; x++) {
      var f1 = 1e9, f2 = 1e9;
      for (i = 0; i < n; i++) {
        var dx = Math.abs(x - pts[i][0]), dy = Math.abs(y - pts[i][1]);
        if (dx > S / 2) dx = S - dx;
        if (dy > S / 2) dy = S - dy;
        var q = dx * dx + dy * dy;
        if (q < f1) { f2 = f1; f1 = q; } else if (q < f2) f2 = q;
      }
      var edge = Math.sqrt(f2) - Math.sqrt(f1), a = Math.pow(Math.max(0, 1 - edge / 22), 2.6), o = (y * S + x) * 4;
      img.data[o] = img.data[o + 1] = img.data[o + 2] = 255; img.data[o + 3] = a * 255;
    }
    g.putImageData(img, 0, 0);
    return ctx.createPattern(c, "repeat");
  }

  function makeLife() {
    var colors = ["#4fb0cb", "#ffc145", "#4fb0cb"], count = W > 900 ? 3 : 2;
    schools = [];
    for (var s = 0; s < count; s++) {
      var dir = s % 2 ? -1 : 1;
      var sc = { ax: rnd(s + 2) * W, ay: H * (0.12 + 0.3 * rnd(s + 9)), vx: dir * (14 + rnd(s + 4) * 10), vy: (rnd(s + 6) - 0.5) * 6, color: colors[s], fish: [] };
      var n = 5 + Math.floor(rnd(s + 5) * 3);
      for (var k = 0; k < n; k++) {
        var ox = (rnd(s * 31 + k) - 0.5) * 120, oy = (rnd(s * 17 + k + 9) - 0.5) * 80;
        sc.fish.push({ ox: ox, oy: oy, x: sc.ax + ox, y: sc.ay + oy, vx: sc.vx, vy: sc.vy, size: 5 + rnd(s * 13 + k) * 3, k: k });
      }
      schools.push(sc);
    }
    turtle = { x: W * 0.86, y: H * 0.34, vx: -7, vy: -2 };
  }

  // Easter egg: the shadow of something very large passes over the bottom.
  // It shows up once if you stay a while, or whenever you tap the turtle.
  function summon() {
    if (giant || reduce || !W) return;
    seen = true;
    var len = Math.min(Math.max(W, H) * 0.62, H * 0.95);
    giant = { len: len, x: W + len * 0.6, y: H * 0.36, ang: Math.PI - 0.1, speed: (W + len * 1.3) / 22 };
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = canvas.clientWidth, h = canvas.clientHeight;
    if (w === W && h === H) return;
    var sx = W ? w / W : 1, sy = H ? h / H : 1, first = !schools.length;
    W = w; H = h;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (first) { makeLife(); return; }
    // Keep everything where it is and only rescale positions. Phones fire a
    // resize whenever the address bar shows or hides during scrolling, and the
    // animals must not jump back to their starting places when that happens.
    schools.forEach(function (sc) {
      sc.ax *= sx; sc.ay *= sy;
      sc.fish.forEach(function (f) { f.x *= sx; f.y *= sy; });
    });
    turtle.x *= sx; turtle.y *= sy;
    if (giant) { giant.x *= sx; giant.y *= sy; }
  }

  function step(dt) {
    time += dt;
    if (!seen && time > 40 && window.scrollY < H * 0.5) summon();
    var scare = null;
    if (giant) {
      giant.x += Math.cos(giant.ang) * giant.speed * dt; giant.y += Math.sin(giant.ang) * giant.speed * dt;
      if (giant.x < -giant.len * 0.7) giant = null;
      else scare = [0.28, 0.04, -0.2].map(function (u) {
        return [giant.x + Math.cos(giant.ang) * giant.len * u, giant.y + Math.sin(giant.ang) * giant.len * u];
      });
    }
    schools.forEach(function (sc) {
      sc.ax += sc.vx * dt; sc.ay += Math.sin(time * 0.25 + sc.vx) * 4 * dt;
      var jump = 0;
      if (sc.ax > W + 140) jump = -(W + 280); else if (sc.ax < -140) jump = W + 280;
      if (jump) { sc.ax += jump; sc.ay = H * (0.12 + 0.3 * Math.random()); sc.fish.forEach(function (f) { f.x = sc.ax + f.ox; f.y = sc.ay + f.oy; }); }
      sc.fish.forEach(function (f) {
        var tx = sc.ax + f.ox, ty = sc.ay + f.oy + Math.sin(time * 1.1 + f.k) * 5;
        var ax = (tx - f.x) * 2.5 - (f.vx - sc.vx) * 2.5, ay = (ty - f.y) * 2.5 - (f.vy - sc.vy) * 2.5;
        if (mouse) {
          var dx = f.x - mouse.x, dy = f.y - mouse.y, m = Math.sqrt(dx * dx + dy * dy) || 1;
          if (m < 130) { var push = (1 - m / 130) * 900; ax += dx / m * push; ay += dy / m * push; }
        }
        if (scare) {
          var R = giant.len * 0.3;
          scare.forEach(function (p) {
            var ex = f.x - p[0], ey = f.y - p[1], d = Math.sqrt(ex * ex + ey * ey) || 1;
            if (d < R) { var pu = (1 - d / R) * 700; ax += ex / d * pu; ay += ey / d * pu; }
          });
        }
        f.vx += ax * dt; f.vy += ay * dt; f.x += f.vx * dt; f.y += f.vy * dt;
      });
    });
    turtle.x += turtle.vx * dt; turtle.y += turtle.vy * dt;
    if (turtle.x < -60 || turtle.y < -60) { turtle.x = W + 60; turtle.y = H * (0.25 + 0.2 * Math.random()); }
  }

  function drawFish(f, color, shadow) {
    var L = f.size * 2.2, wag = Math.sin(time * 7 + f.k * 1.7) * 0.5;
    ctx.save();
    ctx.translate(f.x + (shadow ? 7 : 0), f.y + (shadow ? 11 : 0)); ctx.rotate(Math.atan2(f.vy, f.vx));
    ctx.fillStyle = shadow ? SHADOW : color;
    ctx.beginPath(); ctx.ellipse(0, 0, L / 2, f.size / 2, 0, 0, 6.3); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-L / 2 + 2, 0);
    ctx.lineTo(-L / 2 - f.size * 0.9, -f.size * 0.6 + wag * f.size); ctx.lineTo(-L / 2 - f.size * 0.9, f.size * 0.6 + wag * f.size);
    ctx.fill(); ctx.restore();
  }

  // Sea turtle from above: long front flippers that sweep like wings, small
  // rear paddles, a teardrop shell wider at the shoulders.
  function drawTurtle(t, shadow) {
    var flap = Math.sin(time * 1.6), skin = shadow ? SHADOW : "#8ccba4";
    ctx.save(); ctx.translate(t.x + (shadow ? 9 : 0), t.y + (shadow ? 14 : 0)); ctx.rotate(Math.atan2(t.vy, t.vx) + Math.PI / 2);
    ctx.scale(1.15, 1.15);
    ctx.fillStyle = skin;
    [-1, 1].forEach(function (side) {
      // front flipper
      ctx.save(); ctx.translate(side * 11, -11); ctx.scale(side, 1); ctx.rotate(0.1 + flap * 0.42);
      ctx.beginPath(); ctx.moveTo(-2, -4); ctx.quadraticCurveTo(17, -13, 31, 5); ctx.quadraticCurveTo(15, 1, -1, 6); ctx.closePath(); ctx.fill();
      ctx.restore();
      // rear paddle
      ctx.save(); ctx.translate(side * 9, 17); ctx.rotate(side * (-0.55 - flap * 0.12));
      ctx.beginPath(); ctx.ellipse(0, 5, 3.6, 7.5, 0, 0, 6.3); ctx.fill();
      ctx.restore();
    });
    ctx.beginPath(); ctx.ellipse(0, -25, 5.2, 7, 0, 0, 6.3); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-2.5, 20); ctx.lineTo(0, 27); ctx.lineTo(2.5, 20); ctx.fill();
    // shell
    ctx.fillStyle = shadow ? SHADOW : "#5fae86";
    ctx.beginPath(); ctx.moveTo(0, -20);
    ctx.bezierCurveTo(13, -20, 19, -5, 13, 9); ctx.quadraticCurveTo(7, 20, 0, 23);
    ctx.quadraticCurveTo(-7, 20, -13, 9); ctx.bezierCurveTo(-19, -5, -13, -20, 0, -20);
    ctx.fill();
    if (!shadow) {
      // scutes: a row of plates down the middle, ribs out to the rim
      ctx.strokeStyle = "rgba(235,250,240,0.42)"; ctx.lineWidth = 1; ctx.lineJoin = "round";
      ctx.beginPath();
      ctx.moveTo(0, -15); ctx.lineTo(5, -10); ctx.lineTo(5, 9); ctx.lineTo(0, 16); ctx.lineTo(-5, 9); ctx.lineTo(-5, -10); ctx.closePath();
      [-4, 3].forEach(function (y) { ctx.moveTo(-5, y); ctx.lineTo(5, y); });
      [-1, 1].forEach(function (side) {
        [[-10, -15], [-4, -5], [3, 4], [9, 12]].forEach(function (r) { ctx.moveTo(side * 5, r[0]); ctx.lineTo(side * (r[0] < 0 ? 13 : 12 - r[0] * 0.35), r[1]); });
      });
      ctx.stroke();
    }
    ctx.restore();
  }

  // One closed outline, wound the same way as the others so overlaps do not cancel out.
  function poly(pts) {
    var a = 0, i, n = pts.length;
    for (i = 0; i < n; i++) { var p = pts[i], q = pts[(i + 1) % n]; a += p[0] * q[1] - q[0] * p[1]; }
    if (a > 0) pts.reverse();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (i = 1; i < n; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
  }

  // Seen from above: a short, fat, big-headed fish with wide paddle fins.
  function drawGiant(g) {
    var L = g.len, N = 64, i, s, top = [], bot = [];
    var flap = Math.sin(time * 0.9), beat = 0.78 + 0.22 * Math.sin(time * 1.1 + 1);
    function X(s) { return (0.5 - s) * L; }
    function half(s) {
      var p = s < 0.36 ? Math.pow(1 - Math.pow(1 - s / 0.36, 2), 0.45) : 0.1 + 0.9 * Math.pow(1 - (s - 0.36) / 0.64, 1.1);
      return p * L * 0.235;
    }
    function sway(s) { return Math.sin(time * 1.1 - s * 3) * L * 0.012 * s * s; }
    function edge(s, side, out) { return [X(s), sway(s) + side * (half(s) * (out ? 1 : 0.6) + (out || 0) * L)]; }
    // Points along a curve from a to b that bends toward c
    function curve(a, c, b) {
      var out = [], k, u, v;
      for (k = 0; k <= 12; k++) { u = k / 12; v = 1 - u; out.push([v * v * a[0] + 2 * v * u * c[0] + u * u * b[0], v * v * a[1] + 2 * v * u * c[1] + u * u * b[1]]); }
      return out;
    }
    for (i = 0; i <= N; i++) { s = Math.pow(i / N, 1.7); top.push([X(s), sway(s) - half(s)]); bot.push([X(s), sway(s) + half(s)]); }
    ctx.save(); ctx.translate(g.x, g.y); ctx.rotate(g.ang);
    ctx.fillStyle = "rgba(23,63,77,0.13)";
    ctx.beginPath();
    poly(top.concat(bot.reverse()));
    // Fins: wide rounded paddles held out to the sides, slowly rising and falling
    [-1, 1].forEach(function (side) {
      var reach = 0.21 + 0.03 * flap, a1 = edge(0.5, side, reach), a2 = edge(0.72, side, reach * 0.78);
      poly(curve(edge(0.28, side), edge(0.32, side, reach * 1.05), a1).concat(
           curve(a1, edge(0.7, side, reach * 1.08), a2), curve(a2, edge(0.68, side, 0.03), edge(0.56, side))));
    });
    // Tail: wide and notched; it shortens and lengthens as it beats up and down
    var ty = sway(1), x1 = X(1), d = L * beat;
    var up = [x1 - 0.12 * d, ty - L * 0.2], notch = [x1 - 0.04 * d, ty], down = [x1 - 0.12 * d, ty + L * 0.2];
    poly(curve(edge(0.9, -1), [x1 + 0.03 * L, ty - L * 0.15], up).concat(curve(up, [x1 - 0.06 * d, ty - L * 0.07], notch),
         curve(notch, [x1 - 0.06 * d, ty + L * 0.07], down), curve(down, [x1 + 0.03 * L, ty + L * 0.15], edge(0.9, 1))));
    ctx.fill(); ctx.restore();
  }

  function draw() {
    // Water: sky blue, paling toward the bottom edge where it meets the sand
    var g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#9bdcee"); g.addColorStop(0.75, "#c3edf1"); g.addColorStop(1, "#e2f7f3");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);

    if (caustics && caustics.setTransform) {
      [[2.4, time * 5, time * 3, 0.4], [1.7, -time * 4, time * 5, 0.26]].forEach(function (l) {
        caustics.setTransform(new DOMMatrix().translate(l[1], l[2]).scale(l[0]));
        ctx.globalAlpha = l[3]; ctx.fillStyle = caustics; ctx.fillRect(0, 0, W, H);
      });
      ctx.globalAlpha = 1;
    }

    // Shadows on the bottom are what make the water read as clear
    if (giant) drawGiant(giant);
    drawTurtle(turtle, true);
    schools.forEach(function (sc) { sc.fish.forEach(function (f) { drawFish(f, null, true); }); });
    drawTurtle(turtle, false);
    schools.forEach(function (sc) { sc.fish.forEach(function (f) { drawFish(f, sc.color, false); }); });

    // Warm sun from the top-left corner
    var sun = ctx.createRadialGradient(0, 0, 0, 0, 0, Math.max(W, H) * 0.7);
    sun.addColorStop(0, "rgba(255,236,186,0.55)"); sun.addColorStop(1, "rgba(255,236,186,0)");
    ctx.fillStyle = sun; ctx.fillRect(0, 0, W, H);
  }

  function tick(now) {
    var dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    step(dt); draw();
    if (visible) requestAnimationFrame(tick); else running = false;
  }

  function start() {
    if (running || reduce) return;
    running = true; last = 0; requestAnimationFrame(tick);
  }

  hero.addEventListener("pointermove", function (e) {
    var r = canvas.getBoundingClientRect(); mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
  });
  hero.addEventListener("pointerdown", function (e) {
    var r = canvas.getBoundingClientRect(), dx = e.clientX - r.left - turtle.x, dy = e.clientY - r.top - turtle.y;
    if (dx * dx + dy * dy < 2500) summon();
  });
  hero.addEventListener("pointerleave", function () { mouse = null; });
  window.addEventListener("resize", function () { resize(); if (reduce) draw(); });

  // Paint plain water at once, then build the ripple texture and start moving
  // after the page has rendered. The loop stops while the hero is off screen.
  resize();
  draw();
  setTimeout(function () {
    caustics = makeCaustics();
    if (location.hash === "#deep") summon();
    if (reduce) draw(); else start();
  }, 0);
  if (window.IntersectionObserver) new IntersectionObserver(function (es) {
    visible = es[es.length - 1].isIntersecting;
    if (visible && caustics) start();
  }).observe(hero);
})();
