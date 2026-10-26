"""The opening splash: the carton mascot hops in, pops its flaps open, a check springs out, the flaps
close, and the screen fades into the app. Pure CSS, about 2 s, once per visit; it never blocks clicks."""

HTML = """<style>
.sp{position:fixed;inset:0;z-index:2147483600;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:22px;background:radial-gradient(900px 500px at 50% 40%,#13284A 0%,#0A1628 70%);pointer-events:none;
  animation:spOut .55s ease-in 2.05s forwards}
@keyframes spOut{to{opacity:0;visibility:hidden}}
.sp-stage{position:relative;width:170px;height:170px;transform:scale(1.5);margin:30px 0 26px}
.sp-shadow{position:absolute;left:35px;bottom:6px;width:100px;height:16px;border-radius:50%;background:rgba(0,0,0,.45);
  filter:blur(3px);animation:spShadow 2s cubic-bezier(.22,1,.36,1) both}
.sp-box{position:absolute;left:30px;bottom:20px;width:110px;height:92px;animation:spHop 2s cubic-bezier(.22,1,.36,1) both;
  transform-origin:50% 100%}
.sp-body{position:absolute;inset:0;border-radius:10px;background:linear-gradient(160deg,#E5A262,#C98A4B);
  box-shadow:inset -10px -8px 0 rgba(0,0,0,.08)}
.sp-tape{position:absolute;left:44px;top:0;width:22px;height:18px;background:#F2690F;border-radius:0 0 3px 3px}
.sp-eye{position:absolute;top:28px;width:26px;height:26px;border-radius:50%;background:#F5F0E6;animation:spBlink 2s both}
.sp-eye i{position:absolute;left:8px;top:8px;width:12px;height:12px;border-radius:50%;background:#F2690F}
.sp-eye.l{left:20px}.sp-eye.r{left:64px}
.sp-mouth{position:absolute;left:42px;top:62px;width:26px;height:12px;border:4px solid #0E1B2E;border-top:0;
  border-radius:0 0 18px 18px}
.sp-cheek{position:absolute;top:58px;width:12px;height:8px;border-radius:50%;background:rgba(242,138,90,.55)}
.sp-cheek.l{left:9px}.sp-cheek.r{left:89px}
.sp-flap{position:absolute;top:-6px;width:56px;height:9px;border-radius:3px;background:#A86F38}
.sp-flap.l{left:0;transform-origin:0 100%;animation:spFlapL 2s cubic-bezier(.34,1.56,.64,1) both}
.sp-flap.r{right:0;transform-origin:100% 100%;animation:spFlapR 2s cubic-bezier(.34,1.56,.64,1) both}
.sp-check{position:absolute;left:62px;top:40px;width:46px;height:46px;border-radius:50%;background:#2ECC71;
  display:flex;align-items:center;justify-content:center;color:#0E1B2E;font:900 28px/1 Inter,Arial,sans-serif;
  box-shadow:0 8px 20px rgba(46,204,113,.35);animation:spCheck 2s cubic-bezier(.34,1.56,.64,1) both}
.sp-word{font:800 34px/1 'Plus Jakarta Sans',Inter,Arial,sans-serif;color:#EAF0F7;letter-spacing:-.5px;
  animation:spUp .7s cubic-bezier(.22,1,.36,1) .25s both}
.sp-word b{color:#FF8A3D}
.sp-line{font:500 15px/1.4 Inter,Arial,sans-serif;color:#9FB0C6;animation:spUp .7s cubic-bezier(.22,1,.36,1) .4s both}
.sp-bar{width:220px;height:4px;border-radius:99px;background:#1E3352;overflow:hidden;animation:spUp .7s ease .5s both}
.sp-bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#F2690F,#FF8A3D);
  animation:spGrow 1.6s cubic-bezier(.4,0,.2,1) .4s forwards}
@keyframes spHop{0%{transform:translateY(-120px) scale(.9,1.1);opacity:0}18%{transform:translateY(0) scale(1.12,.86);opacity:1}
  28%{transform:translateY(0) scale(.96,1.05)}36%{transform:none}62%{transform:none}70%{transform:translateY(-18px) scale(.97,1.04)}
  80%{transform:translateY(0) scale(1.06,.94)}88%,100%{transform:none}}
@keyframes spShadow{0%{transform:scale(.4);opacity:0}18%{transform:scale(1.1);opacity:1}70%{transform:scale(.8)}80%,100%{transform:scale(1)}}
@keyframes spFlapL{0%,34%{transform:rotate(0)}46%,70%{transform:rotate(-125deg)}82%,100%{transform:rotate(0)}}
@keyframes spFlapR{0%,34%{transform:rotate(0)}46%,70%{transform:rotate(125deg)}82%,100%{transform:rotate(0)}}
@keyframes spCheck{0%,40%{transform:translate(-50%,0) scale(0);opacity:0}52%{transform:translate(-50%,-78px) scale(1.1);opacity:1}
  66%{transform:translate(-50%,-70px) scale(1);opacity:1}76%,100%{transform:translate(-50%,0) scale(0);opacity:0}}
@keyframes spBlink{0%,56%,60%,100%{transform:scaleY(1)}58%{transform:scaleY(.1)}}
@keyframes spUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes spGrow{to{width:100%}}
@media (prefers-reduced-motion:reduce){.sp{animation:spOut .3s ease-in .6s forwards}
  .sp *{animation:none!important;opacity:1!important}.sp-check{display:none}}
</style>
<div class="sp" role="presentation" aria-hidden="true">
  <div class="sp-stage">
    <div class="sp-shadow"></div>
    <div class="sp-box">
      <div class="sp-check">✓</div>
      <div class="sp-body"></div>
      <div class="sp-flap l"></div><div class="sp-flap r"></div>
      <div class="sp-tape"></div>
      <div class="sp-eye l"><i></i></div><div class="sp-eye r"><i></i></div>
      <div class="sp-cheek l"></div><div class="sp-cheek r"></div>
      <div class="sp-mouth"></div>
    </div>
  </div>
  <div class="sp-word">Oops<b>-Proof</b></div>
  <div class="sp-line">Checking every shipment before it leaves…</div>
  <div class="sp-bar"><i></i></div>
</div>"""
