/*! font-scale — 变老说明书站点的「字号」调节
 *
 *  读者里中老年人不少，默认字号偏小；调大以后要能在翻章、翻篇、重开浏览器之后
 *  还是那个大小。做法：倍率写进 localStorage（键 aging-font-scale），设到 <html> 的
 *  --aging-scale 上（extra.css 用它算全站字号）。页面 <head> 里另有一段内联脚本
 *  先按存下来的值设一遍，避免打开时先小后大地闪一下。
 *
 *  位置：优先放进页眉，排在白天黑夜按钮前面（读者最容易找到的地方）；
 *  万一以后 Material 升级动了页眉结构、找不到槽位，就退回左下角浮动，功能不丢。
 *
 *  控件自身尺寸用 px 写死，不跟着 --aging-scale 放大——否则调到 185% 时
 *  按钮和浮层会一起涨大，反过来挡内容。
 *  localStorage 被禁用（隐私模式）时全走默认值，不报错。
 */
(function () {
  "use strict";

  var KEY = "aging-font-scale";
  var HINT_KEY = "aging-font-scale-hint";
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
  function hasSeenHint() {
    try { return window.localStorage.getItem(HINT_KEY) === "1"; } catch (e) { return true; }
  }
  function markHintSeen() {
    try { window.localStorage.setItem(HINT_KEY, "1"); } catch (e) {}
  }
  function paint(v) {
    document.documentElement.style.setProperty("--aging-scale", String(v));
  }
  function pct(v) { return Math.round(v * 100) + "%"; }

  var idx = readIdx();
  paint(STEPS[idx]);   // 尽早设一次；<head> 里那段内联脚本是同一件事的更早一份

  function mount() {
    if (document.querySelector(".aging-font")) return;

    // 找页眉里的槽位：白天黑夜按钮前面（Material 给版本选择器留的就是这个位置）
    var host = document.querySelector(".md-header__inner");
    var slot = document.querySelector(".md-header__option")
            || document.querySelector(".md-header__source")
            || document.querySelector(".md-search")
            || null;
    var where = (host && slot) ? "header" : "float";   // 注意：别用 place 当变量名，会和下面的 place() 定位函数撞名

    var box = document.createElement("div");
    box.className = "aging-font";
    box.dataset.place = where;
    box.innerHTML =
      '<button type="button" class="aging-font__toggle" aria-label="调整正文字号" aria-expanded="false" title="调整字号">字号</button>' +
      '<div class="aging-font__pop" hidden>' +
        '<div class="af-row">' +
          '<button type="button" class="af-btn af-dec" aria-label="把字调小一点">A−</button>' +
          '<span class="af-pct" aria-live="polite"></span>' +
          '<button type="button" class="af-btn af-inc" aria-label="把字调大一点">A+</button>' +
        '</div>' +
        '<button type="button" class="af-reset">恢复默认</button>' +
        '<p class="af-tip">换章节、关掉浏览器再回来，都还是这个大小。</p>' +
      '</div>' +
      '<div class="af-hint" role="status">字太小？点这里调大，翻到别的章节也不会变回去。</div>';

    if (where === "header") {
      slot.parentNode.insertBefore(box, slot);
    } else {
      document.body.appendChild(box);
    }

    var toggle = box.querySelector(".aging-font__toggle");
    var pop = box.querySelector(".aging-font__pop");
    var out = box.querySelector(".af-pct");
    var btnDec = box.querySelector(".af-dec");
    var btnInc = box.querySelector(".af-inc");

    function refresh() {
      var v = STEPS[idx];
      paint(v);
      out.textContent = pct(v);
      btnDec.disabled = idx === 0;
      btnInc.disabled = idx === STEPS.length - 1;
      box.querySelector(".af-reset").textContent = "恢复默认（" + pct(STEPS[STEPS.indexOf(DEFAULT)]) + "）";
    }
    // 按按钮当前位置算浮层坐标，并夹在视口内：手机上按钮靠右，纯 CSS 居中会顶出屏幕
    function place(el) {
      if (!el) return;
      var r = toggle.getBoundingClientRect();
      var w = el.offsetWidth || 208;
      var vw = document.documentElement.clientWidth;
      el.style.position = "fixed";
      el.style.transform = "none";
      el.style.left = Math.round(Math.min(Math.max(8, r.left + r.width / 2 - w / 2), vw - w - 8)) + "px";
      el.style.right = "auto";
      el.style.top = Math.round(r.bottom + 6) + "px";
      el.style.bottom = "auto";
    }
    function open(on) {
      pop.hidden = !on;
      toggle.setAttribute("aria-expanded", on ? "true" : "false");
      if (on) { place(pop); hideHint(); }
    }
    window.addEventListener("resize", function () { if (!pop.hidden) place(pop); if (hint.classList.contains("af-on")) place(hint); });
    window.addEventListener("scroll", function () { if (!pop.hidden) place(pop); if (hint.classList.contains("af-on")) place(hint); }, { passive: true });
    function hideHint() {
      hint.classList.remove("af-on");
      markHintSeen();
    }

    var hint = box.querySelector(".af-hint");

    toggle.addEventListener("click", function (e) {
      e.preventDefault();
      open(pop.hidden);
    });
    btnDec.addEventListener("click", function () { if (idx > 0) { idx--; save(STEPS[idx]); refresh(); } });
    btnInc.addEventListener("click", function () { if (idx < STEPS.length - 1) { idx++; save(STEPS[idx]); refresh(); } });
    box.querySelector(".af-reset").addEventListener("click", function () {
      idx = STEPS.indexOf(DEFAULT); save(STEPS[idx]); refresh();
    });
    document.addEventListener("click", function (e) { if (!box.contains(e.target)) open(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") open(false); });

    refresh();

    if (!hasSeenHint()) {
      window.setTimeout(function () { place(hint); hint.classList.add("af-on"); }, 1200);
      window.setTimeout(hideHint, 14000);
    }
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
