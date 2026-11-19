// Hero: still, clear, shallow water in the sun. Light ripples across a sandy
// bottom, a few fish and one sea turtle pass slowly above the text, and the
// fish move aside for the cursor. Nothing else.
(function () {
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  var canvas = document.getElementById("water");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var hero = canvas.parentElement;
  var reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SHADOW = "rgba(23,63,77,0.10)";
  var W = 0, H = 0, time = 0, last = 0, mouse = null, caustics = null, schools = [], turtle = null;

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
  }

  function step(dt) {
    time += dt;
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

  function drawTurtle(t, shadow) {
    var flap = Math.sin(time * 1.8) * 0.4;
    ctx.save(); ctx.translate(t.x + (shadow ? 9 : 0), t.y + (shadow ? 14 : 0)); ctx.rotate(Math.atan2(t.vy, t.vx) + Math.PI / 2);
    ctx.fillStyle = shadow ? SHADOW : "#8ccba4";
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
      ctx.save(); ctx.translate(s[0] * 13, s[1] * (s[1] < 0 ? 10 : 14)); ctx.rotate(s[0] * (s[1] < 0 ? 0.9 + flap : 2.3 - flap * 0.5));
      ctx.beginPath(); ctx.ellipse(0, -8, s[1] < 0 ? 5 : 4, s[1] < 0 ? 13 : 8, 0, 0, 6.3); ctx.fill(); ctx.restore();
    });
    ctx.beginPath(); ctx.ellipse(0, -24, 6, 7, 0, 0, 6.3); ctx.fill();
    ctx.fillStyle = shadow ? SHADOW : "#64b389";
    ctx.beginPath(); ctx.ellipse(0, 0, 16, 20, 0, 0, 6.3); ctx.fill();
    ctx.restore();
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
    requestAnimationFrame(tick);
  }

  hero.addEventListener("pointermove", function (e) {
    var r = canvas.getBoundingClientRect(); mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
  });
  hero.addEventListener("pointerleave", function () { mouse = null; });
  window.addEventListener("resize", function () { resize(); if (reduce) draw(); });

  caustics = makeCaustics();
  resize();
  if (reduce) draw(); else requestAnimationFrame(tick);
})();
