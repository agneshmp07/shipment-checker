"""The Oops-Proof mascot: a low-poly 3D shipping carton whose face is the brand mark (cream eyes,
orange-dot pupils). It turns its whole body to follow the pointer, a finger or the phone's tilt,
looks worried at the preview card while it is Blocked, hops when it turns Ready, and spins when tapped.

Rendered with three.js (r128, cdnjs) into the hero. Without WebGL, or with reduced motion, the
flat brand mark stays in its place.
"""
from __future__ import annotations

import base64
from pathlib import Path

_MARK = base64.b64encode((Path(__file__).resolve().parent.parent / "assets" / "mark.svg").read_bytes()).decode()

# a box cutter for the cursor: orange handle, steel blade pointing at the hotspot (top-left)
_CUTTER = base64.b64encode(b"""<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
<path d="M3 3 L12 7 L9 10 Z" fill="#DCE3EA" stroke="#0E1B2E" stroke-width="1.2" stroke-linejoin="round"/>
<rect x="9" y="8" width="20" height="8" rx="3" transform="rotate(42 9 8)" fill="#F2690F" stroke="#0E1B2E" stroke-width="1.4"/>
<circle cx="17" cy="16" r="1.6" fill="#0E1B2E"/></svg>""").decode()

HTML = f"""<div class="sc-mascot" aria-label="Oops-Proof mascot: a cardboard carton that watches your shipment">
  <img class="sc-mascot-flat" alt="" src="data:image/svg+xml;base64,{_MARK}">
  <div class="sc-bubble"><b>3 items checked</b><br>counts match the booking ✓</div>
  <div class="sc-hint">✂ Tap the box to inspect it</div>
</div>"""

CSS = """
.sc-mascot{position:absolute;inset:0;cursor:url("data:image/svg+xml;base64,""" + _CUTTER + """") 3 3, pointer;
  animation:scFade .8s ease-out .15s both}
.sc-bubble{position:absolute;z-index:3;left:2%;top:2%;padding:10px 14px;border-radius:14px 14px 14px 4px;background:#F5F0E6;
  color:#0E1B2E;font-size:.82rem;line-height:1.35;box-shadow:0 12px 30px rgba(0,0,0,.35);pointer-events:none;
  opacity:0;transform:translateY(8px) scale(.96);transition:opacity .35s ease,transform .45s cubic-bezier(.22,1,.36,1)}
.sc-bubble b{color:#C2410C}
.sc-mascot.inspecting .sc-bubble.on{opacity:1;transform:none}
.sc-hint{position:absolute;z-index:2;left:8%;bottom:2%;font-size:.78rem;color:#B9C8DC;background:rgba(14,27,46,.7);
  border:1px solid #2A4A75;padding:5px 11px;border-radius:99px;pointer-events:none;transition:opacity .5s;
  animation:scFadeUp .8s cubic-bezier(.22,1,.36,1) 4.6s both}
.sc-mascot.used .sc-hint{animation:none;opacity:0}
.sc-mascot canvas{position:absolute;inset:0;width:100%!important;height:100%!important;outline:none}
.sc-mascot-flat{position:absolute;left:50%;top:50%;width:120px;height:120px;transform:translate(-50%,-50%);
  border-radius:28px;transition:opacity .4s}
.sc-mascot.live .sc-mascot-flat{opacity:0}
@media (max-width:760px){.sc-mascot{position:relative;inset:auto;height:300px}}
"""

JS = """<script>
(() => {
  if (window.__opMascot) return; window.__opMascot = true;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pointer = {x: null, y: null, at: 0};
  const point = (x, y) => { pointer.x = x; pointer.y = y; pointer.at = performance.now(); };
  addEventListener('pointermove', e => point(e.clientX, e.clientY), {passive: true});
  addEventListener('touchmove', e => e.touches[0] && point(e.touches[0].clientX, e.touches[0].clientY), {passive: true});
  addEventListener('deviceorientation', e => {
    const box = document.querySelector('.sc-mascot'); if (!box || e.gamma == null) return;
    const r = box.getBoundingClientRect();
    point(r.left + r.width / 2 + e.gamma * 14, r.top + r.height / 2 + ((e.beta || 45) - 45) * 10);
  }, {passive: true});

  function withThree(cb) {
    if (window.THREE) return cb();
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
    s.onload = cb; document.head.appendChild(s);
  }

  function build(box) {
    const T = window.THREE;
    let renderer;
    try { renderer = new T.WebGLRenderer({antialias: true, alpha: true}); } catch (e) { return null; }
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.outputEncoding = T.sRGBEncoding;
    box.appendChild(renderer.domElement);
    const scene = new T.Scene();
    const camera = new T.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 0.5, 7.4); camera.lookAt(0, 0.05, 0);

    scene.add(new T.HemisphereLight(0xfff1e0, 0x0a1628, 0.55));
    const key = new T.DirectionalLight(0xfff0dc, 1.6); key.position.set(3.5, 5, 6); scene.add(key);
    const fill = new T.DirectionalLight(0x9fc3ff, 0.35); fill.position.set(-5, 1, 3); scene.add(fill);
    const rim = new T.PointLight(0xff7a2a, 2.2, 14); rim.position.set(-3.5, 2, -3); scene.add(rim);

    const flat = c => new T.MeshStandardMaterial({color: new T.Color(c).convertSRGBToLinear(), flatShading: true,
                                                 roughness: 0.82, metalness: 0});
    const cardboard = flat(0xc98a4b), cardboardDark = flat(0xa86f38), tape = flat(0xf2690f);
    const cream = flat(0xf5f0e6), navy = flat(0x0e1b2e), orange = flat(0xf2690f);

    // low-poly: jitter the box vertices a little so the facets catch the light
    function faceted(w, h, d, seg, amt) {
      const g = new T.BoxGeometry(w, h, d, seg, seg, seg), p = g.attributes.position, seen = {};
      for (let i = 0; i < p.count; i++) {
        const k = [p.getX(i), p.getY(i), p.getZ(i)].map(v => v.toFixed(3)).join();
        if (!seen[k]) seen[k] = [(Math.random() - .5) * amt, (Math.random() - .5) * amt, (Math.random() - .5) * amt];
        p.setXYZ(i, p.getX(i) + seen[k][0], p.getY(i) + seen[k][1], p.getZ(i) + seen[k][2]);
      }
      g.computeVertexNormals(); return g;
    }

    const rig = new T.Group(); scene.add(rig);           // turns toward the pointer
    const wide = () => box.clientWidth > 420;            // desktop: carton left of centre, card at lower right
    const bodyG = new T.Group(); rig.add(bodyG);          // hops, breathes, spins
    const body = new T.Mesh(faceted(2.3, 1.85, 1.75, 3, 0.07), cardboard); bodyG.add(body);
    // top flaps, slightly open, and the tape across them
    const flapL = new T.Mesh(faceted(1.12, 0.07, 1.74, 2, 0.03), cardboardDark);
    flapL.geometry.translate(0.56, 0, 0); flapL.position.set(-1.15, 0.95, 0); flapL.rotation.z = 0.06; bodyG.add(flapL);
    const flapR = new T.Mesh(faceted(1.12, 0.07, 1.74, 2, 0.03), cardboardDark);
    flapR.geometry.translate(-0.56, 0, 0); flapR.position.set(1.15, 0.95, 0); flapR.rotation.z = -0.06; bodyG.add(flapR);
    // the top tape, in two halves (one on each flap) so cutting the seam opens the box
    const tapeL = new T.Mesh(new T.BoxGeometry(0.22, 0.03, 1.86), tape); tapeL.position.set(1.01, 0.05, 0); flapL.add(tapeL);
    const tapeR = new T.Mesh(new T.BoxGeometry(0.22, 0.03, 1.86), tape); tapeR.position.set(-1.01, 0.05, 0); flapR.add(tapeR);
    const slit = new T.Mesh(new T.BoxGeometry(0.03, 0.035, 1.86), navy); slit.position.set(0, 1.0, 0); slit.scale.z = 0.001;
    slit.visible = false; bodyG.add(slit);
    const inside = new T.Mesh(new T.PlaneGeometry(2.1, 1.6), flat(0x3a2412)); inside.rotation.x = -Math.PI / 2;
    inside.position.y = 0.935; bodyG.add(inside);
    // the box cutter: orange handle, steel blade
    const cutter = new T.Group(); cutter.visible = false; bodyG.add(cutter);
    const handle = new T.Mesh(new T.BoxGeometry(0.2, 0.2, 0.95), flat(0xfacc15)); handle.position.set(0, 0.3, -0.45); cutter.add(handle);
    const grip = new T.Mesh(new T.BoxGeometry(0.21, 0.08, 0.55), navy); grip.position.set(0, 0.36, -0.55); cutter.add(grip);
    const steel = new T.MeshStandardMaterial({color: 0xe6edf3, metalness: 0.6, roughness: 0.25});
    const blade = new T.Mesh(new T.BoxGeometry(0.04, 0.26, 0.34), steel); blade.position.set(0, 0.12, 0.13); blade.rotation.x = 0.6; cutter.add(blade);
    cutter.rotation.set(-0.4, 0.75, 0); cutter.scale.setScalar(1.15);
    // the inventory inside: a mug, a folded shirt and a small box, each with a check badge
    const badgeTex = (() => {
      const c = document.createElement('canvas'); c.width = c.height = 128; const g = c.getContext('2d');
      g.fillStyle = '#2ECC71'; g.beginPath(); g.arc(64, 64, 58, 0, Math.PI * 2); g.fill();
      g.strokeStyle = '#fff'; g.lineWidth = 16; g.lineCap = 'round'; g.lineJoin = 'round';
      g.beginPath(); g.moveTo(36, 66); g.lineTo(56, 86); g.lineTo(92, 46); g.stroke();
      const t = new T.CanvasTexture(c); t.encoding = T.sRGBEncoding; return t;
    })();
    const items = [];
    const addItem = (mesh, x) => {
      const g = new T.Group(); g.add(mesh); g.position.set(x, 0.2, 0); g.visible = false; bodyG.add(g);
      const badge = new T.Sprite(new T.SpriteMaterial({map: badgeTex, transparent: true, depthTest: false}));
      badge.position.set(0, 0.42, 0); badge.scale.setScalar(0.001); g.add(badge);
      items.push({g, badge});
    };
    const mug = new T.Group();
    mug.add(new T.Mesh(new T.CylinderGeometry(0.2, 0.18, 0.34, 12), cream));
    const mugHandle = new T.Mesh(new T.TorusGeometry(0.09, 0.03, 6, 12), cream); mugHandle.position.x = 0.21; mug.add(mugHandle);
    addItem(mug, -0.62);
    const shirt = new T.Group();
    shirt.add(new T.Mesh(new T.BoxGeometry(0.56, 0.1, 0.42), flat(0x3b82f6)));
    const collar = new T.Mesh(new T.BoxGeometry(0.2, 0.02, 0.08), flat(0x1e40af)); collar.position.set(0, 0.06, -0.15); shirt.add(collar);
    addItem(shirt, 0);
    const parcel = new T.Group();
    parcel.add(new T.Mesh(faceted(0.34, 0.34, 0.34, 1, 0.01), cardboardDark));
    parcel.add(new T.Mesh(new T.BoxGeometry(0.08, 0.35, 0.35), tape));
    addItem(parcel, 0.62);
    const tapeFront = new T.Mesh(new T.BoxGeometry(0.44, 0.22, 0.03), tape); tapeFront.position.set(0, 0.88, 0.93); bodyG.add(tapeFront);
    // a navy shipping label on the side with the brand "o"
    const label = new T.Mesh(new T.BoxGeometry(0.03, 0.62, 0.86), navy); label.position.set(1.165, 0.05, 0.1); bodyG.add(label);
    const labelO = new T.Mesh(new T.TorusGeometry(0.16, 0.055, 8, 18), cream); labelO.rotation.y = Math.PI / 2;
    labelO.position.set(1.185, 0.05, 0.1); bodyG.add(labelO);
    const labelDot = new T.Mesh(new T.SphereGeometry(0.07, 8, 6), orange); labelDot.position.set(1.19, 0.25, 0.3); bodyG.add(labelDot);

    // the face: brand eyes (cream with orange-dot pupils), brows, cheeks, mouth
    const face = new T.Group(); face.position.set(0, -0.06, 0.93); bodyG.add(face);
    const eyes = [-0.48, 0.48].map(x => {
      const e = new T.Group(); e.position.set(x, 0.12, 0); face.add(e);
      const white = new T.Mesh(new T.CylinderGeometry(0.33, 0.33, 0.06, 16), cream); white.rotation.x = Math.PI / 2; e.add(white);
      const pupil = new T.Mesh(new T.SphereGeometry(0.15, 12, 10), orange); pupil.position.z = 0.07; e.add(pupil);
      const shine = new T.Mesh(new T.CircleGeometry(0.04, 8), cream); shine.position.set(0.05, 0.06, 0.18); pupil.add(shine);
      return {e, pupil};
    });
    const brows = [-0.48, 0.48].map((x, i) => {
      const b = new T.Mesh(new T.BoxGeometry(0.42, 0.075, 0.04), navy); b.position.set(x, 0.55, 0.01); face.add(b);
      b.userData.side = i ? 1 : -1; return b;
    });
    [-0.85, 0.85].forEach(x => {
      const c = new T.Mesh(new T.CircleGeometry(0.13, 12), new T.MeshBasicMaterial({color: 0xf28a5a, transparent: true, opacity: .45}));
      c.position.set(x, -0.22, 0.005); face.add(c);
    });
    const mouth = new T.Mesh(new T.TorusGeometry(0.2, 0.045, 6, 16, Math.PI), navy); mouth.position.set(0, -0.3, 0.01); face.add(mouth);

    // soft shadow on the "floor"
    const sc = document.createElement('canvas'); sc.width = sc.height = 128;
    const sx = sc.getContext('2d'), gr = sx.createRadialGradient(64, 64, 4, 64, 64, 62);
    gr.addColorStop(0, 'rgba(0,0,0,.55)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); sx.fillStyle = gr; sx.fillRect(0, 0, 128, 128);
    const shadow = new T.Mesh(new T.PlaneGeometry(3.4, 1.3), new T.MeshBasicMaterial({map: new T.CanvasTexture(sc), transparent: true, depthWrite: false}));
    shadow.rotation.x = -Math.PI / 2; shadow.position.y = -1.42; scene.add(shadow);

    const now = () => performance.now() / 1000;
    const state = {hopAt: -1, spinAt: -1, inspectAt: -1, blinkAt: now() + 2.2, blinkStart: -1, mood: 0, start: now(), last: now()};
    // springs: time-based, so the motion is the same at 30, 60 or 120 fps; a little under-damped
    // so turns settle with a soft, natural overshoot instead of stopping dead
    const spring = (x = 0) => ({x, v: 0});
    const step = (s, target, dt, hz, zeta = 0.78) => {
      const w = 2 * Math.PI * hz; s.v += (w * w * (target - s.x) - 2 * zeta * w * s.v) * dt; s.x += s.v * dt; return s.x;
    };
    const yaw = spring(0.45), pitch = spring(0.1), rigX = spring(0), lookX = spring(0), lookY = spring(0);
    const ease = q => q < .5 ? 4 * q * q * q : 1 - Math.pow(-2 * q + 2, 3) / 2;          // ease-in-out cubic
    const smooth = (a, b, x) => { const q = Math.min(1, Math.max(0, (x - a) / (b - a))); return q * q * (3 - 2 * q); };
    // tap: cut the tape, open the flaps, check the inventory, then close up again
    const bubble = box.querySelector('.sc-bubble');
    const INSPECT = 5.8;
    box.addEventListener('pointerdown', () => {
      if (state.inspectAt > 0 && now() - state.inspectAt < INSPECT) return;
      state.inspectAt = now(); box.classList.add('inspecting', 'used');
    });
    let visible = true;
    new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(box);   // rest when off-screen

    function resize() {
      const w = box.clientWidth, h = box.clientHeight; if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    resize(); new ResizeObserver(resize).observe(box);

    function frame() {
      if (!box.isConnected) { renderer.dispose(); return; }
      requestAnimationFrame(frame);
      const t = now(), dt = Math.min(1 / 30, t - state.last); state.last = t;
      if (!visible) return;
      const since = t - state.start;

      // where to look: the pointer, else the booking card (first seconds), else an idle wandering gaze
      let ty, tp;
      if (pointer.x !== null && performance.now() - pointer.at < 3000) {
        const r = box.getBoundingClientRect();
        ty = Math.max(-1, Math.min(1, (pointer.x - (r.left + r.width / 2)) / 560)) * 0.72;
        tp = Math.max(-1, Math.min(1, (pointer.y - (r.top + r.height / 2)) / 460)) * 0.34;
      } else if (since < 4.4) { ty = wide() ? 0.68 : 0.15; tp = wide() ? 0.3 : 0.28; }
      else {
        ty = 0.17 * (Math.sin(t * 0.31) + 0.6 * Math.sin(t * 0.73 + 1.3)) / 1.6;
        tp = 0.05 * (Math.sin(t * 0.27 + 0.5) + 0.5 * Math.sin(t * 0.61)) / 1.5;
      }
      if (state.inspectAt > 0 && t - state.inspectAt < INSPECT) {
        const k0 = t - state.inspectAt;
        ty = 0.08 * Math.sin(t * 1.2); tp = k0 < 1.25 ? 0.42 : (k0 < 4.6 ? -0.22 : 0.1);
      }
      // the eyes lead, the body follows and leans a little into the turn
      step(lookX, ty, dt, 3.2, 0.9); step(lookY, tp, dt, 3.2, 0.9);
      step(yaw, ty, dt, 1.25); step(pitch, tp, dt, 1.25);
      rig.rotation.y = yaw.x; rig.rotation.x = pitch.x;
      rig.rotation.z = Math.max(-0.09, Math.min(0.09, -yaw.v * 0.05));
      rig.position.x = step(rigX, wide() ? -1.42 : 0, dt, 1.1, 1); shadow.position.x = rig.position.x;
      eyes.forEach(({pupil}) => { pupil.position.x = (lookX.x - yaw.x * 0.4) * 0.17; pupil.position.y = -(lookY.x - pitch.x * 0.4) * 0.22; });

      // mood: worried while the card is Blocked (until ~3.4 s), happy after; the mouth morphs through flat
      if (state.hopAt < 0 && since > 3.4) state.hopAt = t;
      state.mood += ((since > 3.4 ? 1 : 0) - state.mood) * (1 - Math.exp(-dt * 5));
      const m = smooth(0, 1, state.mood);
      brows.forEach(b => { b.rotation.z = b.userData.side * (0.38 * (1 - m) - 0.1 * m); b.position.y = 0.55 + 0.05 * m; });
      mouth.scale.y = 1 - 2 * m; mouth.position.y = -0.36 + 0.12 * m;

      // breathing and float, then the hop: anticipation crouch, stretch in the air, squash on landing
      let y = Math.sin(t * 1.3) * 0.055, sy = 1 + Math.sin(t * 2.1) * 0.012, spin = 0;
      if (state.hopAt > 0) {
        const h = (t - state.hopAt) / 0.85;
        if (h < 1) {
          if (h < 0.18) sy *= 1 - 0.12 * ease(h / 0.18);
          else if (h < 0.78) {
            const q = (h - 0.18) / 0.6;
            y += 0.8 * Math.sin(q * Math.PI);
            sy *= 1 + 0.1 * Math.sin(q * Math.PI) * (q < 0.5 ? 1 : 0.5) - 0.12 * (1 - smooth(0, 0.22, q));
          } else sy *= 1 - 0.1 * Math.sin((h - 0.78) / 0.22 * Math.PI);
        }
      }
      if (state.spinAt > 0) { const q = (t - state.spinAt) / 1.0; if (q < 1) spin = ease(q) * Math.PI * 2; }
      bodyG.position.y = y; bodyG.scale.set(1 / Math.sqrt(sy), sy, 1 / Math.sqrt(sy)); bodyG.rotation.y = spin;
      const lift = Math.max(0, y);
      shadow.scale.setScalar(1 - Math.min(0.45, lift * 0.5)); shadow.material.opacity = 1 - Math.min(0.5, lift * 0.6);

      // the inspection: cut (0.25-1.05 s), open (1.15-1.75), items up (1.55-2.5), hold, items down, close
      const k = state.inspectAt > 0 ? t - state.inspectAt : -1;
      const backOut = q => { const c = 1.7; return 1 + (c + 1) * Math.pow(q - 1, 3) + c * Math.pow(q - 1, 2); };
      const seg = (a, b) => Math.min(1, Math.max(0, (k - a) / (b - a)));
      if (k >= 0 && k < INSPECT) {
        cutter.visible = k < 1.3;
        const drop = ease(seg(0, 0.25)), lift = ease(seg(1.05, 1.3));
        cutter.position.set(0, 1.0 + (1 - drop) * 0.7 + lift * 0.8, 0.95 - 1.9 * ease(seg(0.25, 1.05)));
        cutter.position.x = Math.sin(k * 40) * 0.008 * (k > 0.25 && k < 1.05 ? 1 : 0);   // a little sawing jitter
        slit.visible = k > 0.25 && k < 1.4; slit.scale.z = Math.max(0.001, ease(seg(0.25, 1.05)));
        slit.position.z = 0.93 * (1 - slit.scale.z);
        const open = k < 4.6 ? backOut(seg(1.15, 1.75)) : 1 - ease(seg(4.75, 5.35));
        flapL.rotation.z = 0.06 + 1.85 * open; flapR.rotation.z = -0.06 - 1.85 * open;
        items.forEach(({g, badge}, i) => {
          const up = k < 4.3 ? backOut(seg(1.55 + i * 0.18, 2.15 + i * 0.18)) : 1 - ease(seg(4.3, 4.85));
          g.visible = up > 0.001; g.rotation.y = Math.sin(t * 1.6 + i) * 0.25;
          g.position.y = 0.2 + 1.35 * up + (up > 0.99 ? Math.sin(t * 2.4 + i * 1.3) * 0.04 : 0);
          const b = k < 4.3 ? backOut(seg(2.2 + i * 0.25, 2.55 + i * 0.25)) : 1 - seg(4.2, 4.4);
          badge.scale.setScalar(Math.max(0.001, 0.3 * b));
        });
        bubble.classList.toggle('on', k > 2.7 && k < 4.6);
        if (k > 5.35 && state.hopAt < state.inspectAt) state.hopAt = t;    // all closed again: a happy hop
      } else if (state.inspectAt > 0 && box.classList.contains('inspecting')) {
        cutter.visible = false; slit.visible = false; flapL.rotation.z = 0.06; flapR.rotation.z = -0.06;
        items.forEach(({g}) => { g.visible = false; }); box.classList.remove('inspecting'); bubble.classList.remove('on');
      }

      // blink: a quick, soft close and open
      if (t > state.blinkAt) { state.blinkStart = t; state.blinkAt = t + 3 + Math.random() * 3.5; }
      const b = (t - state.blinkStart) / 0.16;
      const open = b >= 0 && b < 1 ? 1 - 0.9 * Math.sin(b * Math.PI) : 1;
      eyes.forEach(({e}) => { e.scale.y = open; });
      const openNow = k >= 0 && k < INSPECT ? Math.min(ease(seg(1.0, 1.8)), 1 - ease(seg(4.6, 5.5))) : 0;
      camera.position.z = 7.4 + 1.5 * openNow; camera.position.y = 0.5 + 0.55 * openNow;
      camera.lookAt(0, 0.05 + 0.5 * openNow, 0);
      renderer.render(scene, camera);
    }
    box.classList.add('live');
    requestAnimationFrame(frame);
    return true;
  }

  function mountAll() {
    if (reduce) return;
    document.querySelectorAll('.sc-mascot:not([data-mounted])').forEach(box => {
      box.dataset.mounted = '1';
      withThree(() => { if (!build(box)) box.dataset.mounted = 'fail'; });
    });
  }
  mountAll();
  new MutationObserver(mountAll).observe(document.body, {childList: true, subtree: true});
})();
</script>"""
