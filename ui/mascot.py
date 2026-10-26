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

HTML = f"""<div class="sc-mascot" aria-label="Oops-Proof mascot: a cardboard carton that watches your shipment">
  <img class="sc-mascot-flat" alt="" src="data:image/svg+xml;base64,{_MARK}">
</div>"""

CSS = """
.sc-mascot{position:absolute;inset:0;cursor:grab;animation:scFade .8s ease-out .15s both}
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
    const tapeTop = new T.Mesh(new T.BoxGeometry(0.44, 0.03, 1.86), tape); tapeTop.position.set(0, 1.0, 0); bodyG.add(tapeTop);
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

    const state = {yaw: 0.45, pitch: 0.1, hopAt: -1, spinAt: -1, blinkAt: 2.2, mood: 0, start: performance.now() / 1000};
    box.addEventListener('pointerdown', () => { state.spinAt = performance.now() / 1000; state.hopAt = state.spinAt; });

    function resize() {
      const w = box.clientWidth, h = box.clientHeight; if (!w || !h) return;
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    }
    resize(); new ResizeObserver(resize).observe(box);

    const lerp = (a, b, k) => a + (b - a) * k;
    function frame() {
      if (!box.isConnected) { renderer.dispose(); return; }
      const t = performance.now() / 1000, since = t - state.start;
      let ty = 0, tp = 0;
      const live = pointer.x !== null && performance.now() - pointer.at < 3000;
      if (live) {
        const r = box.getBoundingClientRect();
        ty = Math.max(-1, Math.min(1, (pointer.x - (r.left + r.width / 2)) / 520)) * 0.75;
        tp = Math.max(-1, Math.min(1, (pointer.y - (r.top + r.height / 2)) / 420)) * 0.38;
      } else if (since < 4.4) { ty = wide() ? 0.7 : 0.15; tp = wide() ? 0.32 : 0.3; }   // watching the booking card
      else { ty = Math.sin(t * 0.45) * 0.18; tp = Math.sin(t * 0.33) * 0.05; }   // idle look-around
      state.yaw = lerp(state.yaw, ty, 0.08); state.pitch = lerp(state.pitch, tp, 0.08);
      rig.rotation.y = state.yaw; rig.rotation.x = state.pitch;
      rig.position.x = lerp(rig.position.x, wide() ? -1.6 : 0, 0.2); shadow.position.x = rig.position.x;
      eyes.forEach(({pupil}) => { pupil.position.x = lerp(pupil.position.x, ty * 0.16, .2); pupil.position.y = lerp(pupil.position.y, -tp * 0.2, .2); });

      // mood: worried while the card is Blocked (until ~3.4 s), happy after
      if (state.hopAt < 0 && since > 3.4) state.hopAt = t;
      state.mood = lerp(state.mood, since > 3.4 ? 1 : 0, 0.1);
      brows.forEach(b => { b.rotation.z = b.userData.side * (0.38 * (1 - state.mood) - 0.1 * state.mood); b.position.y = 0.55 + 0.05 * state.mood; });
      mouth.rotation.z = state.mood > .5 ? Math.PI : 0; mouth.position.y = state.mood > .5 ? -0.24 : -0.36;

      // hop with squash and stretch; tap = hop + spin
      let y = Math.sin(t * 1.4) * 0.06, sy = 1 + Math.sin(t * 2.2) * 0.012, spin = 0;
      if (state.hopAt > 0) {
        const h = (t - state.hopAt) / 0.62;
        if (h < 1) { y += Math.sin(h * Math.PI) * 0.75; sy *= h < .15 ? 1 - h * 1.2 : 1 + Math.sin(h * Math.PI) * 0.08; }
      }
      if (state.spinAt > 0) { const s = (t - state.spinAt) / 0.9; if (s < 1) spin = (1 - Math.pow(1 - s, 3)) * Math.PI * 2; }
      bodyG.position.y = y; bodyG.scale.set(1 / Math.sqrt(sy), sy, 1 / Math.sqrt(sy)); bodyG.rotation.y = spin;
      shadow.scale.setScalar(1 - Math.min(0.45, Math.max(0, y) * 0.5)); shadow.material.opacity = 1 - Math.min(.5, Math.max(0, y) * .6);

      // blink
      if (t - state.start > state.blinkAt) { state.blinkAt = t - state.start + 3 + Math.random() * 3.5; state.blinkUntil = t + 0.13; }
      const bl = state.blinkUntil && t < state.blinkUntil ? 0.1 : 1;
      eyes.forEach(({e}) => { e.scale.y = lerp(e.scale.y, bl, 0.6); });
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
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
