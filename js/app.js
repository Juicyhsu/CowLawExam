/* ── 律師國考刷題系統 app.js ── */
'use strict';

window.App = (function () {

  /* ══════════════════════════════════════════════
     狀態
  ══════════════════════════════════════════════ */
  var S = {
    lawSubject : null,
    topic      : null,
    mode       : 'concept',
    answers    : {},
    reviewed   : {},
    pool       : [],
    idx        : 0,
    token      : localStorage.getItem('jwt') || null,
    userEmail  : localStorage.getItem('userEmail') || null,
    mview      : 'quiz',
    touchX     : 0,
    sidebarOpen: true
  };

  /* ══════════════════════════════════════════════
     工具
  ══════════════════════════════════════════════ */
  var API = 'http://localhost:5000';

  function apiHeaders() {
    var h = { 'Content-Type': 'application/json' };
    if (S.token) h['Authorization'] = 'Bearer ' + S.token;
    return h;
  }
  function $q(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $a(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }
  function mk(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls)  e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function show(id) { var e = $q('#' + id); if (e) e.classList.remove('hidden'); }
  function hide(id) { var e = $q('#' + id); if (e) e.classList.add('hidden'); }
  function isMobile() { return window.innerWidth <= 768; }
  function escHtml(s) {
    if (typeof s !== 'string') return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function lsName(lsId) {
    return lsId || '';  // id IS the Chinese name
  }

  /* ══════════════════════════════════════════════
     進度：localStorage
  ══════════════════════════════════════════════ */
  function loadLocalProgress() {
    try {
      S.answers  = JSON.parse(localStorage.getItem('answers')  || '{}');
      S.reviewed = JSON.parse(localStorage.getItem('reviewed') || '{}');
    } catch(e) {}
  }
  function saveLocalProgress() {
    localStorage.setItem('answers',  JSON.stringify(S.answers));
    localStorage.setItem('reviewed', JSON.stringify(S.reviewed));
  }

  /* ══════════════════════════════════════════════
     進度：伺服器
  ══════════════════════════════════════════════ */
  function loadServerProgress() {
    if (!S.token) return;
    fetch(API + '/api/progress', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (d.answers)            Object.assign(S.answers, d.answers);
        if (d.reviewed_concepts)  d.reviewed_concepts.forEach(function(id){ S.reviewed[id] = true; });
        saveLocalProgress();
        renderTopicList();
        updateStatBadge();
      }).catch(function(){});
  }

  function syncToServer() {
    if (!S.token) return;
    var reviewed_list = Object.keys(S.reviewed).filter(function(k){ return S.reviewed[k]; });
    fetch(API + '/api/progress', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ answers: S.answers, reviewed_concepts: reviewed_list })
    }).catch(function(){});
  }

  /* ── 清除紀錄 ───────────────────────────────── */
  function clearAllProgress() {
    if (!confirm('確定要清除所有答題紀錄與複習標記？此操作無法復原。')) return;
    S.answers = {}; S.reviewed = {};
    saveLocalProgress();
    renderTopicList();
    updateStatBadge();
    if (S.token) {
      fetch(API + '/api/progress', { method: 'DELETE', headers: apiHeaders(),
        body: JSON.stringify({}), 'Content-Type': 'application/json' })
        .then(function(){ alert('紀錄已清除（雲端同步完成）'); })
        .catch(function(){ alert('本機紀錄已清除，雲端同步失敗'); });
    } else {
      alert('本機紀錄已清除');
    }
    if (S.mode === 'quiz' && S.pool.length) renderQuestion();
    if (S.mode === 'concept') renderConceptArea();
  }

  function clearSubjectProgress() {
    var lawSub = S.lawSubject;
    if (!lawSub) { alert('請先選擇一個科目'); return; }
    if (!confirm('確定要清除「' + lawSub + '」的所有答題紀錄？此操作無法復原。')) return;
    // 找出該科目的所有題目 ID
    var ids = window.QDB.questions
      .filter(function(q){ return q.law_subject === lawSub; })
      .map(function(q){ return q.id; });
    // 本機清除
    ids.forEach(function(id){ delete S.answers[id]; });
    saveLocalProgress();
    renderTopicList();
    updateStatBadge();
    if (S.token) {
      fetch(API + '/api/progress', {
        method: 'DELETE', headers: apiHeaders(),
        body: JSON.stringify({ question_ids: ids })
      })
        .then(function(){ alert('「' + lawSub + '」進度已清除（雲端同步完成）'); })
        .catch(function(){ alert('本機已清除，雲端同步失敗'); });
    } else {
      alert('「' + lawSub + '」進度已清除');
    }
    if (S.mode === 'quiz' && S.pool.length) renderQuestion();
  }

  /* ══════════════════════════════════════════════
     帳號 UI
  ══════════════════════════════════════════════ */
  function updateAuthUI() {
    var btn = $q('#auth-btn');
    if (S.userEmail) {
      btn.textContent = S.userEmail.split('@')[0];
      $q('#auth-user-email').textContent = S.userEmail;
      show('auth-loggedin'); hide('auth-login'); hide('auth-register');
    } else {
      btn.textContent = '登入';
      hide('auth-loggedin'); show('auth-login'); hide('auth-register');
    }
  }

  function initAuthPanel() {
    $q('#auth-btn').addEventListener('click', function(e){
      e.stopPropagation();
      $q('#auth-panel').classList.toggle('hidden');
    });
    document.addEventListener('click', function(e){
      var p = $q('#auth-panel');
      if (!p.classList.contains('hidden') && !p.contains(e.target) && e.target !== $q('#auth-btn'))
        p.classList.add('hidden');
    });
    $a('.atab').forEach(function(btn){
      btn.addEventListener('click', function(){
        $a('.atab').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        var t = btn.dataset.atab;
        if (t==='login')    { show('auth-login');    hide('auth-register'); }
        if (t==='register') { show('auth-register'); hide('auth-login'); }
      });
    });
    $q('#btn-login').addEventListener('click', doLogin);
    $q('#login-pw').addEventListener('keydown', function(e){ if (e.key==='Enter') doLogin(); });
    $q('#btn-register').addEventListener('click', doRegister);
    $q('#reg-pw').addEventListener('keydown', function(e){ if (e.key==='Enter') doRegister(); });
    $q('#btn-logout').addEventListener('click', doLogout);
    $q('#btn-clear-subject').addEventListener('click', clearSubjectProgress);
    $q('#btn-clear-progress').addEventListener('click', clearAllProgress);
  }

  function doLogin() {
    var email = $q('#login-email').value.trim();
    var pw    = $q('#login-pw').value;
    var msg   = $q('#login-msg');
    msg.textContent = '登入中…'; msg.className = 'auth-msg';
    fetch(API + '/api/login', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ email: email, password: pw })
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.error) { msg.textContent = d.error; msg.className = 'auth-msg err'; return; }
      setLoggedIn(d.token, d.email);
      msg.textContent = '登入成功！'; msg.className = 'auth-msg ok';
      setTimeout(function(){ $q('#auth-panel').classList.add('hidden'); }, 800);
    }).catch(function(){ msg.textContent = '連線失敗，請確認伺服器是否啟動'; msg.className = 'auth-msg err'; });
  }

  function doRegister() {
    var email = $q('#reg-email').value.trim();
    var pw    = $q('#reg-pw').value;
    var msg   = $q('#reg-msg');
    msg.textContent = '建立中…'; msg.className = 'auth-msg';
    fetch(API + '/api/register', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ email: email, password: pw })
    }).then(function(r){ return r.json(); }).then(function(d){
      if (d.error) { msg.textContent = d.error; msg.className = 'auth-msg err'; return; }
      setLoggedIn(d.token, d.email);
      msg.textContent = '帳號已建立！'; msg.className = 'auth-msg ok';
      setTimeout(function(){ $q('#auth-panel').classList.add('hidden'); }, 800);
    }).catch(function(){ msg.textContent = '連線失敗'; msg.className = 'auth-msg err'; });
  }

  function setLoggedIn(token, email) {
    S.token = token; S.userEmail = email;
    localStorage.setItem('jwt', token);
    localStorage.setItem('userEmail', email);
    updateAuthUI();
    loadServerProgress();
    renderMobileAuth();
  }

  function doLogout() {
    S.token = null; S.userEmail = null;
    localStorage.removeItem('jwt'); localStorage.removeItem('userEmail');
    updateAuthUI();
    $q('#auth-panel').classList.add('hidden');
    renderMobileAuth();
  }

  /* ══════════════════════════════════════════════
     頂部科目 Tab
  ══════════════════════════════════════════════ */
  function initLawTabs() {
    var container = $q('#law-tabs');
    var subs = window.QDB.law_subjects;
    subs.forEach(function(ls, i){
      if (i > 0 && ls.group !== subs[i-1].group)
        container.appendChild(mk('span', 'ltab-sep', '│'));
      var btn = mk('button', 'ltab', ls.id);
      btn.dataset.ls = ls.id;
      btn.addEventListener('click', function(){ selectLawSubject(ls.id); });
      container.appendChild(btn);
    });
    if (subs.length) selectLawSubject(subs[0].id);
  }

  function selectLawSubject(lsId) {
    S.lawSubject = lsId;
    S.topic = null;
    S.pool = []; S.idx = 0;
    $a('.ltab').forEach(function(b){ b.classList.toggle('active', b.dataset.ls === lsId); });
    $q('#sidebar-title').textContent = lsId;
    renderTopicList();
    // 確保顯示正確面板
    if (S.mode === 'concept') {
      show('panel-concept'); hide('panel-quiz');
      renderConceptArea();
    } else {
      hide('panel-concept'); show('panel-quiz');
      $q('#quiz-area').innerHTML = '<div class="placeholder">選好設定後，按「開始練習」</div>';
      hide('quiz-nav');
      $q('#main').classList.remove('quiz-active');
    }
    updateStatBadge();
    if (isMobile()) setMobileView('concept');
  }

  /* ══════════════════════════════════════════════
     主題列表（側邊欄）
  ══════════════════════════════════════════════ */
  function renderTopicList() {
    var container = $q('#topic-list');
    container.innerHTML = '';
    if (!S.lawSubject) return;
    var topicIds = topicsForSubject(S.lawSubject);
    if (!topicIds.length) {
      container.innerHTML = '<div style="padding:12px;color:#888;font-size:.82rem;">此科目尚無主題</div>';
      return;
    }
    topicIds.forEach(function(tid){
      var t = window.QDB.topics[tid];
      var qs_in_topic = window.QDB.questions.filter(function(q){ return q.topic === tid; });
      var total    = qs_in_topic.length;
      var answered = qs_in_topic.filter(function(q){ return S.answers[q.id]; }).length;
      var item = mk('div', 'topic-item' + (S.topic === tid ? ' active' : ''));
      var nameEl = mk('span', 'topic-item-name', escHtml(t.short_name || t.name));
      var pCls   = answered === 0 ? 'zero' : answered === total ? 'done' : 'partial';
      var prog   = mk('span', 'topic-prog ' + pCls, answered + '/' + total);
      item.appendChild(nameEl);
      item.appendChild(prog);
      item.addEventListener('click', function(){ selectTopic(tid); });
      container.appendChild(item);
    });
  }

  function topicsForSubject(lsId) {
    return Object.keys(window.QDB.topics).filter(function(tid){
      return window.QDB.topics[tid].law_subject === lsId;
    }).sort(function(a, b){
      return (window.QDB.topics[b].importance||0) - (window.QDB.topics[a].importance||0);
    });
  }

  function selectTopic(tid) {
    S.topic = tid;
    renderTopicList();
    if (S.mode === 'concept') renderConceptArea();
    else startQuiz();
  }

  /* ══════════════════════════════════════════════
     統計徽章
  ══════════════════════════════════════════════ */
  function updateStatBadge() {
    if (!S.lawSubject) { $q('#stat-badge').textContent = ''; return; }
    var qs_sub  = window.QDB.questions.filter(function(q){ return q.law_subject === S.lawSubject; });
    var total   = qs_sub.length;
    var answered= qs_sub.filter(function(q){ return S.answers[q.id]; }).length;
    var correct = qs_sub.filter(function(q){ return S.answers[q.id] && S.answers[q.id].correct; }).length;
    $q('#stat-badge').textContent = answered > 0
      ? '已答 ' + answered + '/' + total + ' 正確率 ' + Math.round(correct/answered*100) + '%'
      : '共 ' + total + ' 題';
  }

  /* ══════════════════════════════════════════════
     模式切換
  ══════════════════════════════════════════════ */
  function initModeTabs() {
    $a('.mtab').forEach(function(btn){
      btn.addEventListener('click', function(){
        $a('.mtab').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        S.mode = btn.dataset.mode;
        if (S.mode === 'concept') {
          show('panel-concept'); hide('panel-quiz');
          renderConceptArea();
        } else {
          hide('panel-concept'); show('panel-quiz');
        }
        updateMbarActive();
      });
    });
  }

  /* ══════════════════════════════════════════════
     概念複習
  ══════════════════════════════════════════════ */
  function renderConceptArea() {
    var nav   = $q('#concept-topic-nav');
    var hdr   = $q('#concept-header');
    var area  = $q('#concept-area');
    hdr.innerHTML = '';

    if (!S.lawSubject) {
      if (nav) nav.innerHTML = '';
      area.innerHTML = '<div class="placeholder">← 請從左側或上方科目選擇開始複習</div>';
      return;
    }

    // ── 主題 chip 導覽列 ────────────────────────
    var topicIds = topicsForSubject(S.lawSubject);
    if (nav) {
      nav.innerHTML = '';
      // 「全部」chip
      var allChip = mk('button', 'ctopic-chip' + (!S.topic ? ' active' : ''), '全部');
      allChip.addEventListener('click', function(){
        S.topic = null;
        renderConceptArea();
      });
      nav.appendChild(allChip);
      topicIds.forEach(function(tid){
        var t = window.QDB.topics[tid];
        var imp = t.importance >= 8 ? 'high' : t.importance >= 5 ? 'medium' : 'low';
        var chip = mk('button',
          'ctopic-chip imp-chip-' + imp + (S.topic === tid ? ' active' : ''),
          escHtml(t.short_name || t.name));
        chip.title = t.name + '（歷年 ' + t.count + ' 題）';
        chip.addEventListener('click', function(){
          S.topic = tid;
          renderConceptArea();
          // 同步側欄
          $a('.topic-item').forEach(function(item){
            item.classList.toggle('active', item.dataset.tid === tid);
          });
        });
        nav.appendChild(chip);
      });
    }

    // ── 標題 ───────────────────────────────────
    var titleText = S.lawSubject;
    if (S.topic && window.QDB.topics[S.topic]) titleText += ' ▸ ' + window.QDB.topics[S.topic].name.split('｜').pop();
    hdr.innerHTML = '<h2>' + escHtml(titleText) + ' 概念複習</h2>';

    // ── 取得概念卡 ──────────────────────────────
    var targetTopics = S.topic ? [S.topic] : topicIds;
    area.innerHTML = '';

    targetTopics.forEach(function(tid){
      var t = window.QDB.topics[tid];
      // 1. 手動卡片（優先）
      var manual = (window.FLASHCARDS || []).filter(function(c){ return c.topic === tid; });
      if (manual.length) {
        manual.forEach(function(c){ area.appendChild(buildConceptCard(c)); });
      }
      // 2. 考點彙整卡（從真實考題提取，一律顯示）
      var gen = (window.GENERATED_FLASHCARDS || []).filter(function(c){ return c.topic === tid; });
      if (gen.length) {
        gen.forEach(function(c){ area.appendChild(buildConceptCard(c)); });
      } else if (!manual.length) {
        // 手動和生成都沒有時才用自動佔位卡
        area.appendChild(buildConceptCard(autoCard(tid, t)));
      }
    });

    if (!area.children.length)
      area.innerHTML = '<div class="placeholder">此主題尚無概念卡</div>';
  }

  function autoCard(tid, t) {
    var qsInTopic = window.QDB.questions.filter(function(q){ return q.topic === tid; });
    var total = qsInTopic.length;
    var years = [...new Set(qsInTopic.map(function(q){ return q.year; }))].sort().reverse();
    var kws = (t.kw || []);
    var backLines = [];
    if (kws.length) backLines.push('【核心考點關鍵字】\n' + kws.map(function(k){ return '• ' + k; }).join('\n'));
    backLines.push('【歷年出題統計】共 ' + total + ' 題（' + (years.slice(0,3).join('、') + (years.length>3 ? '…等' : '') + '年') + '）');
    backLines.push('【複習建議】\n先理解本主題核心法條，再透過「考題練習」確認應考方向。');
    var imp = t.importance >= 8 ? 'high' : t.importance >= 5 ? 'medium' : 'low';
    return {
      id: 'auto_' + tid,
      topic: tid,
      law_subject: t.law_subject,
      front: (t.short_name || t.name),
      back: backLines.join('\n\n'),
      law_basis: '',
      tags: kws.slice(0, 5),
      importance: imp
    };
  }

  function buildConceptCard(c) {
    var isReviewed = !!S.reviewed[c.id];
    var impCls = 'imp-' + (c.importance || 'medium');
    var isGen = c.id && c.id.startsWith('gen_');
    var card = mk('div', 'concept-card' + (isGen ? ' gen-card' : ''));
    // 換行處理：先轉義 HTML，再把 \n 換成 <br>
    var backHtml = escHtml(c.back).replace(/\n/g, '<br>');
    card.innerHTML =
      '<div class="concept-card-head">' +
        '<span class="cc-imp-dot ' + impCls + '"></span>' +
        '<span class="cc-title">' + escHtml(c.front) + '</span>' +
        (isReviewed ? '<span class="cc-reviewed-badge">✓ 已複習</span>' : '') +
        '<span class="cc-chevron">▶</span>' +
      '</div>' +
      '<div class="concept-card-body">' +
        '<div class="cc-back">' + backHtml + '</div>' +
        (c.law_basis ? '<div class="cc-law">📜 ' + escHtml(c.law_basis) + '</div>' : '') +
        (c.tags && c.tags.length ? '<div class="cc-tags">' + c.tags.map(function(t){ return '<span class="cc-tag">' + escHtml(t) + '</span>'; }).join('') + '</div>' : '') +
        '<button class="cc-reviewed-btn' + (isReviewed ? ' marked' : '') + '" data-cid="' + escHtml(c.id) + '">' +
          (isReviewed ? '✓ 已複習' : '標記為已複習') +
        '</button>' +
      '</div>';

    card.querySelector('.concept-card-head').addEventListener('click', function(){
      card.classList.toggle('expanded');
    });
    card.querySelector('.cc-reviewed-btn').addEventListener('click', function(e){
      e.stopPropagation();
      var btn = e.currentTarget;
      var cid = btn.dataset.cid;
      S.reviewed[cid] = !S.reviewed[cid];
      saveLocalProgress(); syncToServer();
      // 只更新按鈕文字與 badge，不重繪整個區域（避免卡片縮回）
      var isNowReviewed = !!S.reviewed[cid];
      btn.textContent = isNowReviewed ? '✓ 已複習' : '標記為已複習';
      btn.classList.toggle('marked', isNowReviewed);
      var head = card.querySelector('.concept-card-head');
      var badge = head.querySelector('.cc-reviewed-badge');
      if (isNowReviewed && !badge) {
        var b = document.createElement('span');
        b.className = 'cc-reviewed-badge';
        b.textContent = '✓ 已複習';
        head.insertBefore(b, head.querySelector('.cc-chevron'));
      } else if (!isNowReviewed && badge) {
        badge.remove();
      }
      updateStatBadge();
    });
    return card;
  }

  /* ══════════════════════════════════════════════
     考題練習
  ══════════════════════════════════════════════ */
  function initFilterBar() {
    var yc = $q('#year-checks');
    yc.innerHTML = '';
    (window.QDB.years || []).slice().sort().forEach(function(y){
      var lbl = mk('label', 'year-chk');
      lbl.innerHTML = '<input type="checkbox" value="' + y + '" checked> ' + y + '年';
      yc.appendChild(lbl);
    });
    $q('#year-all').addEventListener('click',  function(){ $a('#year-checks input').forEach(function(c){ c.checked=true; }); });
    $q('#year-none').addEventListener('click', function(){ $a('#year-checks input').forEach(function(c){ c.checked=false; }); });
    $q('#btn-start').addEventListener('click', startQuiz);
    $q('#q-prev').addEventListener('click', function(){ goQuestion(-1); });
    $q('#q-next').addEventListener('click', function(){ goQuestion(1); });
  }

  function startQuiz() {
    if (!S.lawSubject) { alert('請先選擇科目'); return; }
    var years = $a('#year-checks input:checked').map(function(c){ return parseInt(c.value); });
    var questions = window.QDB.questions.filter(function(q){
      if (q.law_subject !== S.lawSubject) return false;
      if (!years.includes(q.year)) return false;
      if (S.topic && q.topic !== S.topic) return false;
      return true;
    });
    if (!questions.length) {
      $q('#quiz-area').innerHTML = '<div class="placeholder">沒有符合條件的題目，請調整篩選條件</div>';
      return;
    }
    var order = $q('input[name="qorder"]:checked');
    var orderVal = order ? order.value : 'by_topic';
    if (orderVal === 'by_topic') {
      // 依主題重要度排序；同主題內較新年份優先
      questions = questions.slice().sort(function(a, b){
        var ia = window.QDB.topics[a.topic] ? (window.QDB.topics[a.topic].importance||0) : 0;
        var ib = window.QDB.topics[b.topic] ? (window.QDB.topics[b.topic].importance||0) : 0;
        if (ib !== ia) return ib - ia;
        if (a.topic !== b.topic) return a.topic < b.topic ? -1 : 1;
        return b.year - a.year; // 同主題：新年份先
      });
    } else {
      // 依序：年份由新到舊，同年份按題號排
      questions = questions.slice().sort(function(a, b){
        if (a.year !== b.year) return b.year - a.year;
        return a.num - b.num;
      });
    }
    S.pool = questions;
    S.idx  = 0;
    show('quiz-nav');
    $q('#main').classList.add('quiz-active');
    renderQuestion();
  }

  /* ── 題目卡 ─────────────────────────────────── */
  function renderQuestion() {
    var q    = S.pool[S.idx];
    if (!q) return;
    var area = $q('#quiz-area');
    area.innerHTML = '';

    var card = mk('div', 'q-card');
    var t    = q.topic && window.QDB.topics[q.topic] ? window.QDB.topics[q.topic] : null;
    var topicName = t ? (t.short_name || t.name) : '';

    // 【114年 第35題】標題 + 科目/主題資訊
    card.innerHTML =
      '<div class="q-num-label">【' + q.year + '年 第' + q.num + '題】</div>' +
      '<div class="q-meta">' + escHtml(q.law_subject) + (topicName ? ' ／ ' + escHtml(topicName) : '') + '</div>' +
      '<div class="q-stem">' + escHtml(q.question) + '</div>' +
      '<div class="opts"></div>';

    var optsDiv  = card.querySelector('.opts');
    var answered = S.answers[q.id];

    ['A','B','C','D'].forEach(function(letter){
      if (!q.options || !q.options[letter]) return;
      var btn = mk('button', 'opt-btn', '(' + letter + ')　' + escHtml(q.options[letter]));
      btn.dataset.letter = letter;
      if (answered) {
        btn.disabled = true;
        if (letter === q.answer) btn.classList.add('correct');
        else if (letter === answered.choice) btn.classList.add('wrong');
      }
      btn.addEventListener('click', function(){
        if (S.answers[q.id]) return;
        var correct = letter === q.answer;
        S.answers[q.id] = { choice: letter, correct: correct };
        saveLocalProgress(); syncToServer();
        $a('.opt-btn', card).forEach(function(b){
          b.disabled = true;
          if (b.dataset.letter === q.answer) b.classList.add('correct');
          else if (b.dataset.letter === letter && !correct) b.classList.add('wrong');
        });
        showExplanation(card, q);
        renderTopicList(); updateStatBadge();
      });
      optsDiv.appendChild(btn);
    });

    if (answered) {
      showExplanation(card, q);
      // 「重新選擇」按鈕
      var retryBtn = mk('button', 'btn-retry', '↺ 清除本題記錄（重新選擇）');
      retryBtn.addEventListener('click', function(){
        delete S.answers[q.id];
        saveLocalProgress(); syncToServer();
        renderQuestion();
        renderTopicList(); updateStatBadge();
      });
      card.insertBefore(retryBtn, card.querySelector('.expl-box'));
    }
    area.appendChild(card);

    // 進度列
    $q('#q-progress').textContent = (S.idx + 1) + ' / ' + S.pool.length;
    var tried   = S.pool.slice(0, S.idx+1).filter(function(qq){ return S.answers[qq.id]; }).length;
    var correct = S.pool.slice(0, S.idx+1).filter(function(qq){ return S.answers[qq.id] && S.answers[qq.id].correct; }).length;
    $q('#q-score').textContent = tried ? '答對 ' + correct + '/' + tried : '';
    if (isMobile()) window.scrollTo(0, 0);
  }

  function goQuestion(delta) {
    var n = S.idx + delta;
    if (n < 0 || n >= S.pool.length) return;
    S.idx = n;
    renderQuestion();
  }

  /* ── 詳解 ─────────────────────────────────────  */
  function showExplanation(card, q) {
    var old = card.querySelector('.expl-box');
    if (old) old.remove();
    card.appendChild(buildExplBox(q));
  }

  function buildExplBox(q) {
    var box      = mk('div', 'expl-box');
    var answered = S.answers[q.id];
    var correct  = q.answer;
    var stored   = window.EXPLANATIONS && window.EXPLANATIONS[q.id];

    box.appendChild(mk('div', 'expl-title', '📝 詳解'));

    var banner = mk('div', 'expl-correct-banner');
    banner.textContent = '✔ 正確答案：(' + correct + ')';
    box.appendChild(banner);

    var optsDiv = mk('div', 'expl-opts');
    ['A','B','C','D'].forEach(function(letter){
      if (!q.options || !q.options[letter]) return;
      var isOk  = letter === correct;
      var storedOpt = stored && stored.options && stored.options[letter];
      var label  = storedOpt && storedOpt.label  ? storedOpt.label  : '';
      var reason = storedOpt && storedOpt.reason ? storedOpt.reason : '';

      var optDiv = mk('div', 'expl-opt ' + (isOk ? 'ok' : 'ng'));

      var headText = '【(' + letter + ')】' + (isOk ? '✅ 正確' : '❌ 錯誤') +
        (label ? '（' + label + '）' : '') +
        (isOk && !label ? '——故為本題答案' : '');
      var head = mk('div', 'expl-opt-head');
      head.innerHTML =
        '<span class="expl-opt-icon">' + (isOk ? '✅' : '❌') + '</span>' +
        '<span>' + escHtml(headText.replace(/^【\(.\)】[✅❌]\s?/, '【(' + letter + ')】')) + '</span>';
      optDiv.appendChild(head);

      if (reason) {
        var body = mk('div', 'expl-opt-body', '理由：' + escHtml(reason));
        optDiv.appendChild(body);
      }
      optsDiv.appendChild(optDiv);
    });
    box.appendChild(optsDiv);

    // 核心概念
    if (stored && stored.concept) {
      var cb = mk('div', 'expl-concept');
      cb.innerHTML = '<div class="expl-concept-label">🔑 核心概念</div>' + escHtml(stored.concept);
      box.appendChild(cb);
    } else if (q.topic && window.QDB.topics[q.topic]) {
      var topicObj = window.QDB.topics[q.topic];
      var topicDispName = topicObj.name.split('｜').pop();
      var kws = topicObj.kw || [];
      var conceptText = '本題考點：' + topicDispName +
        (kws.length ? '（' + kws.slice(0, 4).join('、') + '）' : '') +
        '。\n尚無人工詳解，請點選下方「AI 追問」輸入問題以獲取解析。';
      var cb = mk('div', 'expl-concept');
      cb.innerHTML = '<div class="expl-concept-label">🔑 核心概念</div>' + escHtml(conceptText);
      box.appendChild(cb);
    }

    // 補充
    if (stored && stored.supplement) {
      var sb = mk('div', 'expl-supplement');
      sb.innerHTML = '<div class="expl-supplement-label">⚠️ 補充提醒</div>' + escHtml(stored.supplement);
      box.appendChild(sb);
    }

    // 法條備註
    if (stored && stored.law_basis) {
      var lb = mk('div', 'expl-lawbasis');
      lb.innerHTML = '<div class="expl-lawbasis-label">📜 相關法條</div>' + escHtml(stored.law_basis);
      box.appendChild(lb);
    }

    box.appendChild(buildAiChat(q));
    return box;
  }

  /* ── AI 問答 ─────────────────────────────────── */
  function buildAiChat(q) {
    var box = mk('div', 'ai-chat-box');
    box.innerHTML =
      '<div class="ai-chat-label">🤖 AI 追問（需啟動後端伺服器）</div>' +
      '<div class="ai-chat-row">' +
        '<textarea class="ai-chat-input" placeholder="對這題有疑問？請輸入後按送出…" rows="2"></textarea>' +
        '<button class="ai-chat-btn">送出</button>' +
      '</div>' +
      '<div class="ai-answer" style="display:none"></div>';
    var textarea = box.querySelector('.ai-chat-input');
    var sendBtn  = box.querySelector('.ai-chat-btn');
    var ansDiv   = box.querySelector('.ai-answer');
    sendBtn.addEventListener('click', function(){
      var userQ = textarea.value.trim();
      if (!userQ) return;
      sendBtn.disabled = true; sendBtn.textContent = '傳送中…';
      ansDiv.style.display = 'none';
      var ctx = q.year + '年 ' + q.law_subject + '\n題目：' + q.question + '\n選項：\n' +
        ['A','B','C','D'].filter(function(l){ return q.options && q.options[l]; })
          .map(function(l){ return '(' + l + ') ' + q.options[l]; }).join('\n') +
        '\n正確答案：(' + q.answer + ')';
      fetch(API + '/api/ask', {
        method:'POST', headers: apiHeaders(),
        body: JSON.stringify({ question_context: ctx, user_question: userQ })
      }).then(function(r){ return r.json(); }).then(function(d){
        ansDiv.style.display = '';
        if (d.error) { ansDiv.className='ai-answer err'; ansDiv.textContent=d.error; }
        else {
          ansDiv.className='ai-answer';
          // markdown 轉換：跨行粗體、換行、清理多餘的 * 符號
          var html = escHtml(d.answer)
            .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')  // 粗體（含跨行）
            .replace(/\n{3,}/g, '\n\n')                              // 壓縮多餘空行
            .replace(/\n/g, '<br>')
            .replace(/^(\*|-)\s+/gm, '• ');                         // 列表符號
          ansDiv.innerHTML = html;
        }
      }).catch(function(){
        ansDiv.style.display = ''; ansDiv.className='ai-answer err';
        ansDiv.textContent = '連線失敗，請確認伺服器是否啟動 (http://localhost:5000)';
      }).finally(function(){ sendBtn.disabled=false; sendBtn.textContent='送出'; });
    });
    return box;
  }

  /* ══════════════════════════════════════════════
     手機 Tab Bar
  ══════════════════════════════════════════════ */
  function initMobileTabBar() {
    $a('.mbar-btn').forEach(function(btn){
      btn.addEventListener('click', function(){ setMobileView(btn.dataset.mview); });
    });
  }

  function setMobileView(view) {
    if (!isMobile()) return;
    S.mview = view;
    updateMbarActive();
    $a('.mobile-view').forEach(function(v){ v.classList.add('hidden'); });
    if (view === 'subjects') {
      show('mview-subjects');
    } else if (view === 'account') {
      show('mview-account'); renderMobileAuth();
    } else if (view === 'concept') {
      hide('panel-quiz'); show('panel-concept');
      hide('quiz-nav'); $q('#main').classList.remove('quiz-active');
      $a('.mtab').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='concept'); });
      S.mode = 'concept'; renderConceptArea();
    } else if (view === 'quiz') {
      hide('panel-concept'); show('panel-quiz');
      $a('.mtab').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='quiz'); });
      S.mode = 'quiz';
      if (S.pool.length) {
        show('quiz-nav'); $q('#main').classList.add('quiz-active');
      }
    }
  }

  function updateMbarActive() {
    $a('.mbar-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.mview === S.mview); });
  }

  function initMobileSubjectList() {
    var list = $q('#mobile-subject-list');
    list.innerHTML = '';
    window.QDB.law_subjects.forEach(function(ls){
      var btn = mk('button', 'msub-btn', escHtml(ls.id));
      btn.dataset.ls = ls.id;
      btn.addEventListener('click', function(){
        $a('.msub-btn').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        selectLawSubject(ls.id);
        setMobileView('concept');
      });
      list.appendChild(btn);
    });
  }

  function renderMobileAuth() {
    var area = $q('#mobile-auth-area');
    if (!area) return;
    if (S.userEmail) {
      area.innerHTML =
        '<p style="font-weight:600;margin-bottom:6px">' + escHtml(S.userEmail) + '</p>' +
        '<p style="color:#888;font-size:.85rem;margin-bottom:14px">進度已同步至雲端 ☁️</p>' +
        '<button class="btn-outline w100" id="m-logout-btn">登出</button>' +
        '<button class="btn-danger w100" style="margin-top:8px" id="m-clear-btn">清除所有紀錄</button>';
      $q('#m-logout-btn').addEventListener('click', doLogout);
      $q('#m-clear-btn').addEventListener('click', clearAllProgress);
    } else {
      area.innerHTML =
        '<p style="color:#888;font-size:.88rem;margin-bottom:14px">登入後可同步答題進度至雲端</p>' +
        '<input class="auth-input" type="email" id="m-login-email" placeholder="Email">' +
        '<input class="auth-input" type="password" id="m-login-pw" placeholder="密碼">' +
        '<button class="btn-primary w100" id="m-btn-login">登入</button>' +
        '<div class="auth-msg" id="m-login-msg"></div>' +
        '<hr style="margin:14px 0;border:none;border-top:1px solid #eee">' +
        '<p style="font-size:.82rem;color:#888;margin-bottom:8px">還沒帳號？</p>' +
        '<input class="auth-input" type="email" id="m-reg-email" placeholder="Email">' +
        '<input class="auth-input" type="password" id="m-reg-pw" placeholder="密碼（6字元以上）">' +
        '<button class="btn-outline w100" id="m-btn-register">建立帳號</button>' +
        '<div class="auth-msg" id="m-reg-msg"></div>';
      $q('#m-btn-login').addEventListener('click', function(){
        var email=$q('#m-login-email').value.trim(), pw=$q('#m-login-pw').value, msg=$q('#m-login-msg');
        msg.textContent='登入中…'; msg.className='auth-msg';
        fetch(API+'/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pw})})
          .then(function(r){return r.json();}).then(function(d){
            if(d.error){msg.textContent=d.error;msg.className='auth-msg err';return;}
            setLoggedIn(d.token,d.email); renderMobileAuth();
          }).catch(function(){msg.textContent='連線失敗';msg.className='auth-msg err';});
      });
      $q('#m-btn-register').addEventListener('click', function(){
        var email=$q('#m-reg-email').value.trim(), pw=$q('#m-reg-pw').value, msg=$q('#m-reg-msg');
        msg.textContent='建立中…'; msg.className='auth-msg';
        fetch(API+'/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email,password:pw})})
          .then(function(r){return r.json();}).then(function(d){
            if(d.error){msg.textContent=d.error;msg.className='auth-msg err';return;}
            setLoggedIn(d.token,d.email); renderMobileAuth();
          }).catch(function(){msg.textContent='連線失敗';msg.className='auth-msg err';});
      });
    }
  }

  /* ══════════════════════════════════════════════
     滑動換題（手機）
  ══════════════════════════════════════════════ */
  function initSwipe() {
    var main = $q('#main');
    main.addEventListener('touchstart', function(e){ S.touchX = e.changedTouches[0].clientX; }, { passive:true });
    main.addEventListener('touchend',   function(e){
      if (S.mode !== 'quiz' || !S.pool.length) return;
      var dx = e.changedTouches[0].clientX - S.touchX;
      if (Math.abs(dx) > 60) goQuestion(dx < 0 ? 1 : -1);
    }, { passive:true });
  }

  /* ══════════════════════════════════════════════
     Sidebar 收合
  ══════════════════════════════════════════════ */
  function initSidebar() {
    $q('#collapse-btn').addEventListener('click', function(){
      S.sidebarOpen = !S.sidebarOpen;
      $q('#sidebar').classList.toggle('collapsed', !S.sidebarOpen);
      $q('#collapse-btn').textContent = S.sidebarOpen ? '◀' : '▶';
    });
  }

  /* ══════════════════════════════════════════════
     初始化
  ══════════════════════════════════════════════ */
  function init() {
    if (window.QDB_OVERRIDES) {
      window.QDB.questions.forEach(function(q) {
        var ov = window.QDB_OVERRIDES[q.id];
        if (ov) Object.assign(q, ov);
      });
    }
    loadLocalProgress();
    initAuthPanel();
    updateAuthUI();
    initLawTabs();
    initModeTabs();
    initFilterBar();
    initMobileTabBar();
    initMobileSubjectList();
    initSwipe();
    initSidebar();
    if (S.token) loadServerProgress();
    updateStatBadge();
  }

  document.addEventListener('DOMContentLoaded', init);

  return {
    selectLawSubject : selectLawSubject,
    selectTopic      : selectTopic,
    goQuestion       : goQuestion,
    startQuiz        : startQuiz,
    clearAllProgress : clearAllProgress
  };

})();
