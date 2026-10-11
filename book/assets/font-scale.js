/*! font-scale — 变老说明书站点的「字大小」调节
 *  为什么有它：这本书的读者里中老年人不少，默认字号偏小；调大以后，
 *  要能在翻章、翻篇、换标签页、重开浏览器之后还是那个大小。
 *  做法：把倍率写进 localStorage（键 aging-font-scale），再设到 <html> 的
 *  --aging-scale 上（extra.css 用它算全站字号）。页面 <head> 里另有一段内联
 *  脚本先按存下来的值设一遍，避免打开时先小后大地闪一下。
 *  后端不可用、localStorage 被禁用（隐私模式）时都退回默认值，不报错。
 */
(function () {
  "use strict";

  var KEY = "aging-font-scale";
  var HINT_KEY = "aging-font-scale-seen";
  var STEPS = [1, 1.15, 1.3, 1.45, 1.65, 1.85];   // 100% → 185%
  var DEFAULT = 1.15;                              // 没设置过时用这一档（比 Material 原字号大一档）

  function readIdx() {
    var v = NaN;
    try { v = parseFloat(window.localStorage.getItem(KEY)); } catch (e) { v = NaN; }
    var i = STEPS.indexOf(v);
    return i < 0 ? STEPS.indexOf(DEFAULT) : i;
  }
  function save(v) {
    try { window.localStorage.setItem(KEY, String(v)); } catch (e) {}
  }
  function paint(v) {
    document.documentElement.style.setProperty("--aging-scale", String(v));
  }
  function pct(v) { return Math.round(v * 100) + "%"; }

  var idx = readIdx();
  paint(STEPS[idx]);

  function mount() {
    if (document.querySelector(".aging-font")) return;

    var box = document.createElement("div");
    box.className = "aging-font";
    box.setAttribute("role", "group");
    box.setAttribute("aria-label", "调整正文字号");
    box.innerHTML =
      '<button type="button" class="af-btn af-dec" aria-label="把字调小一点" title="字小一点">A−</button>' +
      '<button type="button" class="af-btn af-reset" aria-label="恢复到默认字号" title="点一下恢复默认">' +
        '<span class="af-name">字大小</span><span class="af-pct"></span>' +
      '</button>' +
      '<button type="button" class="af-btn af-inc" aria-label="把字调大一点" title="字大一点">A+</button>';

    var hint = document.createElement("div");
    hint.className = "af-hint";
    hint.setAttribute("role", "status");
    hint.textContent = "字太小？点 A+ 调大，翻到别的章节也不会变回去。";

    document.body.appendChild(box);
    document.body.appendChild(hint);

    var out = box.querySelector(".af-pct");
    var btnDec = box.querySelector(".af-dec");
    var btnInc = box.querySelector(".af-inc");

    function refresh() {
      var v = STEPS[idx];
      paint(v);
      out.textContent = pct(v);
      btnDec.disabled = idx === 0;
      btnInc.disabled = idx === STEPS.length - 1;
    }
    function hideHint() {
      hint.classList.remove("af-on");
      try { window.localStorage.setItem(HINT_KEY, "1"); } catch (e) {}
    }

    btnDec.addEventListener("click", function () { if (idx > 0) { idx--; save(STEPS[idx]); refresh(); } hideHint(); });
    btnInc.addEventListener("click", function () { if (idx < STEPS.length - 1) { idx++; save(STEPS[idx]); refresh(); } hideHint(); });
    box.querySelector(".af-reset").addEventListener("click", function () {
      idx = STEPS.indexOf(DEFAULT); save(STEPS[idx]); refresh(); hideHint();
    });

    var seen = false;
    try { seen = window.localStorage.getItem(HINT_KEY) === "1"; } catch (e) {}
    if (!seen) {
      window.setTimeout(function () { hint.classList.add("af-on"); }, 1200);
      window.setTimeout(hideHint, 14000);
    }
    refresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
  // 以后若开启 Material 的即时加载（navigation.instant），换页不重新执行脚本，这里兜住
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(mount);
  }
})();
