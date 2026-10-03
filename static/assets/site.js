/* 다고침집수리 — 모든 페이지 공통 동작 */
(function () {
  // 메뉴 항목을 누르면 모바일 메뉴 닫기
  document.querySelectorAll('.gnb a').forEach(function (a) {
    a.addEventListener('click', function () { document.body.classList.remove('menu-open'); });
  });

  // 시공사례 목록: 분야별 거르기
  var filter = document.querySelector('.filter');
  if (filter) {
    filter.addEventListener('click', function (ev) {
      var b = ev.target.closest('button'); if (!b) return;
      filter.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); x.classList.toggle('ghost', x !== b); });
      var f = b.dataset.f;
      document.querySelectorAll('.fi').forEach(function (el) { el.classList.toggle('hide', f !== 'all' && el.dataset.c !== f); });
    });
  }

  // 사례 사진 크게 보기
  document.querySelectorAll('.gallery.lb a').forEach(function (a) {
    a.addEventListener('click', function (ev) {
      ev.preventDefault();
      var box = document.createElement('div');
      box.className = 'lbx';
      box.innerHTML = '<img alt=""><button aria-label="닫기">×</button>';
      box.querySelector('img').src = a.getAttribute('href');
      box.addEventListener('click', function () { box.remove(); });
      document.body.appendChild(box);
    });
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { var b = document.querySelector('.lbx'); if (b) b.remove(); }
  });

  // 하단 상담 바: 손가락으로 확대해도(iOS) 화면 폭에 맞춰 잘리지 않게
  var vv = window.visualViewport, bar = document.querySelector('.callbar');
  if (vv && bar) {
    var tick = 0;
    var apply = function () {
      tick = 0;
      if (getComputedStyle(bar).display === 'none') { bar.classList.remove('vv-fit'); bar.style.width = bar.style.transform = ''; return; }
      var s = vv.scale || 1;
      if (Math.abs(s - 1) < 0.01) { bar.classList.remove('vv-fit'); bar.style.width = bar.style.transform = ''; return; }
      bar.classList.add('vv-fit');
      bar.style.width = (vv.width * s) + 'px';
      bar.style.transform = 'translate(' + vv.offsetLeft + 'px,' + (vv.offsetTop + vv.height - bar.offsetHeight / s) + 'px) scale(' + (1 / s) + ')';
    };
    var sched = function () { if (!tick) tick = requestAnimationFrame(apply); };
    vv.addEventListener('resize', sched); vv.addEventListener('scroll', sched);
    window.addEventListener('resize', sched); apply();
  }
})();
