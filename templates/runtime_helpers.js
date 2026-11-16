/* ==========================================================================
 * 零版式运行时纯函数底座（可选引入，不创建任何业务 DOM，不规定任何版式或类名）
 * 只封装每个游戏 UI 项目都会重复踩坑的三件事：
 *   1. mountStageScale         —— 单一真源舞台等比缩放（top-left 原点 + 显式居中位移，兼容嵌套 iframe 宿主）
 *   2. createSeamlessVideoPool —— 硬切 + 主备双路提前 0.15s 无缝零黑帧循环 + 按需拉流
 *   3. armOverlaySkip          —— 全屏演出防同次点击穿透的“单击浮出返回、再点跳过”状态机
 * ========================================================================== */
(function (global) {
  function mountStageScale(stageEl, stageW, stageH) {
    document.documentElement.style.setProperty('--stage-w', stageW + 'px');
    document.documentElement.style.setProperty('--stage-h', stageH + 'px');
    stageEl.style.position = 'absolute';
    stageEl.style.left = '0';
    stageEl.style.top = '0';
    stageEl.style.width = stageW + 'px';
    stageEl.style.height = stageH + 'px';
    stageEl.style.transformOrigin = 'top left';
    stageEl.style.isolation = 'isolate';
    function fit() {
      var vw = window.innerWidth;
      var vh = window.innerHeight;
      var s = Math.min(vw / stageW, vh / stageH);
      if (!isFinite(s) || s <= 0) s = 1;
      var tx = (vw - stageW * s) / 2;
      var ty = (vh - stageH * s) / 2;
      stageEl.style.transform = 'translate(' + tx + 'px, ' + ty + 'px) scale(' + s + ')';
    }
    fit();
    window.addEventListener('resize', fit);
    return fit;
  }

  function createSeamlessVideoPool(videoMap, spareEl, srcMap) {
    var currentKey = null;
    var front = null;
    var back = spareEl;
    var pausedAll = false;

    var timer = setInterval(function () {
      if (pausedAll || !front || front.paused || !front.duration) return;
      if (front.currentTime < front.duration - 0.15) return;
      if (!back || back === front || back.dataset.poolKey !== currentKey || back.readyState < 3) return;
      back.currentTime = 0;
      var p = back.play();
      if (p && p.catch) p.catch(function () {});
      back.classList.add('on');
      front.classList.remove('on');
      var old = front;
      front = back;
      back = old;
      setTimeout(function () { if (old !== front) old.pause(); }, 160);
    }, 80);

    return {
      switchTo: function (key) {
        if (!videoMap[key] || !srcMap[key]) return;
        pausedAll = false;
        currentKey = key;
        Object.keys(videoMap).forEach(function (k) {
          if (k !== key) { videoMap[k].classList.remove('on'); videoMap[k].pause(); }
        });
        if (spareEl) { spareEl.classList.remove('on'); spareEl.pause(); }
        var incoming = videoMap[key];
        if (incoming.readyState === 0) incoming.load();
        incoming.currentTime = 0;
        var p = incoming.play();
        if (p && p.catch) p.catch(function () {});
        incoming.classList.add('on');
        front = incoming;
        back = spareEl;
        if (spareEl && spareEl.dataset.poolKey !== key) {
          spareEl.dataset.poolKey = key;
          spareEl.src = srcMap[key];
          spareEl.load();
        }
      },
      pauseAll: function () {
        pausedAll = true;
        Object.keys(videoMap).forEach(function (k) { videoMap[k].pause(); });
        if (spareEl) spareEl.pause();
      },
      resume: function () {
        pausedAll = false;
        if (front) {
          var p = front.play();
          if (p && p.catch) p.catch(function () {});
        }
      },
      destroy: function () { clearInterval(timer); }
    };
  }

  function armOverlaySkip(stageEl, skipBtnEl, onExit) {
    var active = false, armed = false, shown = false;
    stageEl.addEventListener('click', function (e) {
      if (!active || !armed || shown) return;
      if (skipBtnEl.contains(e.target)) return;
      shown = true;
      skipBtnEl.hidden = false;
    });
    skipBtnEl.addEventListener('click', function () {
      if (active) finish();
    });
    function finish() {
      if (!active) return;
      active = false; armed = false; shown = false;
      skipBtnEl.hidden = true;
      onExit();
    }
    return {
      enter: function () {
        active = true; armed = false; shown = false;
        skipBtnEl.hidden = true;
        setTimeout(function () { if (active) armed = true; }, 0);
      },
      finish: finish
    };
  }

  global.GUIRestoreRuntime = {
    mountStageScale: mountStageScale,
    createSeamlessVideoPool: createSeamlessVideoPool,
    armOverlaySkip: armOverlaySkip
  };
})(window);
