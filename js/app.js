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
    bookmarks  : {},      // { qid: true }
    qnotes     : {},      // { qid: 'note text' }
    pool       : [],
    idx        : 0,
    token      : localStorage.getItem('jwt') || null,
    userEmail  : localStorage.getItem('userEmail') || null,
    mview      : 'quiz',
    touchX     : 0,
    sidebarOpen: true,
    quizFilter : 'all',   // 'all' | 'wrong' | 'bookmarked'
    dataMode   : 'default', // 'default' | 'blank'
    important  : {},
    forget     : {}
  };

  var USER_CONCEPT_NOTES = {};  // noteKey -> {front, back, subject, topic_id}
  var CUSTOM_SUBJECTS    = [];  // [{id, label}]

  /* ══════════════════════════════════════════════
     工具
  ══════════════════════════════════════════════ */
  var API = '';

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
      S.answers   = JSON.parse(localStorage.getItem('answers')   || '{}');
      S.reviewed  = JSON.parse(localStorage.getItem('reviewed')  || '{}');
      S.bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '{}');
      S.qnotes    = JSON.parse(localStorage.getItem('qnotes')    || '{}');
      S.important = JSON.parse(localStorage.getItem('concept_important') || '{}');
      S.forget    = JSON.parse(localStorage.getItem('concept_forget')    || '{}');
    } catch(e) {}
  }
  function saveLocalProgress() {
    localStorage.setItem('answers',   JSON.stringify(S.answers));
    localStorage.setItem('reviewed',  JSON.stringify(S.reviewed));
    localStorage.setItem('concept_important', JSON.stringify(S.important));
    localStorage.setItem('concept_forget',    JSON.stringify(S.forget));
  }
  function saveLocalBookmarks() {
    localStorage.setItem('bookmarks', JSON.stringify(S.bookmarks));
  }
  function saveLocalQnotes() {
    localStorage.setItem('qnotes', JSON.stringify(S.qnotes));
  }
  function loadLocalCustomSubjects() {
    try { CUSTOM_SUBJECTS = JSON.parse(localStorage.getItem('custom_subjects') || '[]'); } catch(e) {}
  }
  function saveLocalCustomSubjects() {
    localStorage.setItem('custom_subjects', JSON.stringify(CUSTOM_SUBJECTS));
  }
  function loadLocalConceptNotes() {
    try { USER_CONCEPT_NOTES = JSON.parse(localStorage.getItem('concept_user_notes') || '{}'); } catch(e) {}
  }
  function saveConceptNotesLocal() {
    localStorage.setItem('concept_user_notes', JSON.stringify(USER_CONCEPT_NOTES));
  }
  function loadLocalDataMode() {
    S.dataMode = localStorage.getItem('data_mode') || 'default';
  }
  function saveLocalDataMode() {
    localStorage.setItem('data_mode', S.dataMode);
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

  /* ── 書籤 ───────────────────────────────────── */
  function loadServerBookmarks() {
    if (!S.token) return;
    fetch(API + '/api/bookmarks', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){
        if (Array.isArray(d)) d.forEach(function(qid){ S.bookmarks[qid] = true; });
        saveLocalBookmarks();
        if (S.mode === 'quiz' && S.pool.length) renderQuestion();
      }).catch(function(){});
  }
  function syncBookmarkToServer(qid) {
    if (!S.token) return;
    fetch(API + '/api/bookmarks', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ question_id: qid })
    }).catch(function(){});
  }

  /* ── 題目筆記 ───────────────────────────────── */
  function loadServerQnotes() {
    if (!S.token) return;
    fetch(API + '/api/question_notes', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){ Object.assign(S.qnotes, d); saveLocalQnotes(); })
      .catch(function(){});
  }
  function syncQnote(qid, text) {
    if (!S.token) return;
    fetch(API + '/api/question_notes', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ question_id: qid, note_text: text })
    }).catch(function(){});
  }

  /* ── 概念筆記 ───────────────────────────────── */
  function loadServerConceptNotes() {
    if (!S.token) return;
    fetch(API + '/api/concept_notes', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){
        // 還原刪除與永久刪除標記
        Object.keys(d).forEach(function(k) {
          if (d[k].back === '__DELETED__') {
            d[k]._deleted = true;
          } else if (d[k].back === '__PERM_DELETED__') {
            d[k]._perm_deleted = true;
          }
        });
        Object.assign(USER_CONCEPT_NOTES, d);
        saveConceptNotesLocal();
        if (S.mode === 'concept') renderConceptArea();
      }).catch(function(){});
  }
  function syncConceptNote(noteKey, data) {
    if (!S.token) return;
    var payload = Object.assign({}, data);
    if (payload._deleted) {
      payload.back = '__DELETED__';
    } else if (payload._perm_deleted) {
      payload.back = '__PERM_DELETED__';
    }
    fetch(API + '/api/concept_notes', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify(Object.assign({ note_key: noteKey }, payload))
    }).catch(function(){});
  }
  function deleteConceptNoteServer(noteKey) {
    if (!S.token) return;
    fetch(API + '/api/concept_notes/' + encodeURIComponent(noteKey), {
      method: 'DELETE', headers: apiHeaders()
    }).catch(function(){});
  }

  /* ── 自訂科目（伺服器） ──────────────────────── */
  function loadServerCustomSubjects() {
    if (!S.token) return;
    fetch(API + '/api/user_settings', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){
        var changed = false;
        if (d.custom_subjects && Array.isArray(d.custom_subjects)) {
          d.custom_subjects.forEach(function(cs){
            if (!CUSTOM_SUBJECTS.find(function(x){ return x.id === cs.id; })) {
              CUSTOM_SUBJECTS.push(cs);
              changed = true;
            }
          });
          if (changed) {
            saveLocalCustomSubjects();
            renderCustomSubjectTabs();
          }
        }
        if (d.concept_important) {
          S.important = Object.assign({}, S.important, d.concept_important);
          localStorage.setItem('concept_important', JSON.stringify(S.important));
        }
        if (d.concept_forget) {
          S.forget = Object.assign({}, S.forget, d.concept_forget);
          localStorage.setItem('concept_forget', JSON.stringify(S.forget));
        }
        if (S.mode === 'concept') renderConceptArea();
      }).catch(function(){});
  }
  function syncCustomSubjects() {
    if (!S.token) return;
    fetch(API + '/api/user_settings', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({
        custom_subjects: CUSTOM_SUBJECTS,
        concept_important: S.important,
        concept_forget: S.forget
      })
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
      var panel = $q('#auth-panel');
      panel.classList.toggle('hidden');
      if (!panel.classList.contains('hidden')) {
        // 面板開啟時清除上次殘留的訊息
        ['#login-msg', '#reg-msg'].forEach(function(sel){
          var el = $q(sel); if (el) { el.textContent = ''; el.className = 'auth-msg'; }
        });
      }
    });
    document.addEventListener('click', function(e){
      var p = $q('#auth-panel');
      if (!p.classList.contains('hidden') && !p.contains(e.target) && e.target !== $q('#auth-btn'))
        p.classList.add('hidden');
    });
    $a('.atab').forEach(function(btn){
      btn.addEventListener('click', function(){
        if (S.userEmail) return;  // 已登入時 tab 無效
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
    loadServerAudioNotes();
    loadServerBookmarks();
    loadServerQnotes();
    loadServerConceptNotes();
    loadServerCustomSubjects();
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
  var EXCLUDED_SUBJECTS = ['海商法'];  // 一試不考，剔除

  /* ══════════════════════════════════════════════
     自訂科目
  ══════════════════════════════════════════════ */
  function _deleteCustomSubject(csId, label, desktopWrap) {
    if (!confirm('確定刪除自訂科目「' + label + '」？\n（相關筆記不會刪除）')) return;
    CUSTOM_SUBJECTS = CUSTOM_SUBJECTS.filter(function(x){ return x.id !== csId; });
    saveLocalCustomSubjects();
    syncCustomSubjects();
    if (desktopWrap) desktopWrap.remove();
    else $a('#law-tabs .ltab-custom-wrap').forEach(function(w){ if (w.querySelector('[data-ls="' + csId + '"]')) w.remove(); });
    $a('#mobile-law-tabs .m-ltab-custom-wrap').forEach(function(w){ if (w.querySelector('[data-ls="' + csId + '"]')) w.remove(); });
    var fallback = window.QDB.law_subjects.filter(function(ls){ return !EXCLUDED_SUBJECTS.includes(ls.id); });
    if (S.lawSubject === csId && fallback.length) selectLawSubject(fallback[0].id);
  }

  function makeCustomSubjectTab(cs) {
    var wrap = mk('span', 'ltab-custom-wrap');
    var label = cs.label || cs.id.replace('custom:', '');
    var btn   = mk('button', 'ltab ltab-custom', escHtml(label));
    btn.dataset.ls = cs.id;
    btn.addEventListener('click', function(){ selectLawSubject(cs.id); });
    var del = mk('button', 'ltab-del', '✕');
    del.title = '刪除自訂科目「' + escHtml(label) + '」';
    del.addEventListener('click', function(e){ e.stopPropagation(); _deleteCustomSubject(cs.id, label, wrap); });
    wrap.appendChild(btn);
    wrap.appendChild(del);
    return wrap;
  }

  function makeCustomMobileTab(cs) {
    var label = cs.label || cs.id.replace('custom:', '');
    var wrap = mk('span', 'm-ltab-custom-wrap');
    var btn  = mk('button', 'm-ltab m-ltab-custom', escHtml(label));
    btn.dataset.ls = cs.id;
    btn.addEventListener('click', function(){ selectLawSubject(cs.id); });
    var del = mk('button', 'm-ltab-del', '✕');
    del.title = '刪除自訂科目';
    del.addEventListener('click', function(e){ e.stopPropagation(); _deleteCustomSubject(cs.id, label, null); });
    wrap.appendChild(btn);
    wrap.appendChild(del);
    return wrap;
  }

  function renderCustomSubjectTabs() {
    $a('.ltab-custom-wrap', $q('#law-tabs')).forEach(function(el){ el.remove(); });
    var addBtn = $q('.ltab-add');
    CUSTOM_SUBJECTS.forEach(function(cs){
      if (addBtn) $q('#law-tabs').insertBefore(makeCustomSubjectTab(cs), addBtn);
    });
    $a('#mobile-law-tabs .m-ltab-custom-wrap').forEach(function(el){ el.remove(); });
    var mBar = $q('#mobile-law-tabs');
    if (mBar) {
      var mAddBtn = $q('.m-ltab-add', mBar);
      CUSTOM_SUBJECTS.forEach(function(cs){
        var wrap = makeCustomMobileTab(cs);
        if (mAddBtn) mBar.insertBefore(wrap, mAddBtn);
        else mBar.appendChild(wrap);
      });
    }
  }

  function promptAddCustomSubject() {
    var name = prompt('請輸入新科目名稱（例如：選修科目、民訴整理）：');
    if (!name || !name.trim()) return;
    name = name.trim();
    var id = 'custom:' + name;
    if (CUSTOM_SUBJECTS.find(function(x){ return x.id === id; })) { alert('已有同名科目'); return; }
    var cs = { id: id, label: name };
    CUSTOM_SUBJECTS.push(cs);
    saveLocalCustomSubjects();
    syncCustomSubjects();
    var addBtn = $q('.ltab-add');
    if (addBtn) $q('#law-tabs').insertBefore(makeCustomSubjectTab(cs), addBtn);
    var mBar = $q('#mobile-law-tabs');
    if (mBar) {
      var mAddBtn = $q('.m-ltab-add', mBar);
      var mWrap = makeCustomMobileTab(cs);
      if (mAddBtn) mBar.insertBefore(mWrap, mAddBtn);
      else mBar.appendChild(mWrap);
    }
    selectLawSubject(id);
  }

  function initLawTabs() {
    var container = $q('#law-tabs');
    var subs = window.QDB.law_subjects.filter(function(ls){
      return !EXCLUDED_SUBJECTS.includes(ls.id);
    });
    subs.forEach(function(ls, i){
      if (i > 0 && ls.group !== subs[i-1].group)
        container.appendChild(mk('span', 'ltab-sep', '│'));
      var btn = mk('button', 'ltab', ls.id);
      btn.dataset.ls = ls.id;
      btn.addEventListener('click', function(){ selectLawSubject(ls.id); });
      container.appendChild(btn);
    });
    // 自訂科目：插入已存的自訂科目按鈕
    CUSTOM_SUBJECTS.forEach(function(cs){
      container.appendChild(makeCustomSubjectTab(cs));
    });
    // 「+ 科目」按鈕
    var addBtn = mk('button', 'ltab ltab-add', '✚');
    addBtn.title = '新增自訂科目';
    addBtn.addEventListener('click', promptAddCustomSubject);
    container.appendChild(addBtn);
    if (subs.length) selectLawSubject(subs[0].id);
  }

  function selectLawSubject(lsId) {
    S.lawSubject = lsId;
    S.topic = null;
    S.pool = []; S.idx = 0;
    updateTopicChip();
    renderTopicChipsBar();
    $a('.ltab').forEach(function(b){ b.classList.toggle('active', b.dataset.ls === lsId); });
    $q('#sidebar-title').textContent = lsId.replace(/^custom:/, '');
    renderTopicList();
    // 確保顯示正確面板
    if (S.mode === 'audio') {
      if (!isMobile()) rebuildAudio();   // 桌機聽讀：換科目重建段落
    } else if (S.mode === 'concept') {
      show('panel-concept'); hide('panel-quiz');
      renderConceptArea();
    } else {
      hide('panel-concept'); show('panel-quiz');
      $q('#quiz-area').innerHTML = '<div class="placeholder">選好設定後，按「開始練習」</div>';
      hide('quiz-nav');
      $q('#main').classList.remove('quiz-active');
    }
    updateStatBadge();
    $a('.m-ltab').forEach(function(b){ b.classList.toggle('active', b.dataset.ls === lsId); });
    if (isMobile() && S.mview === 'audio') {
      audStop(); rebuildAudio();
    } else if (isMobile() && S.mview !== 'quiz') {
      setMobileView('concept');
    }
  }

  /* ══════════════════════════════════════════════
     主題列表（側邊欄）
  ══════════════════════════════════════════════ */
  function renderTopicList() {
    var container = $q('#topic-list');
    container.innerHTML = '';
    if (!S.lawSubject) return;

    var isBlank = (S.dataMode === 'blank' && S.mode !== 'quiz');
    if (isBlank) {
      // 自主筆記模式：只顯示使用者在該科目下自己新增的自訂主題
      var customPrefix = S.lawSubject + ':blank_custom_';
      var topicsMap = {};
      var hasUnclassified = false;
      Object.keys(USER_CONCEPT_NOTES).forEach(function(k) {
        if (!k.startsWith(customPrefix)) return;
        var note = USER_CONCEPT_NOTES[k];
        if (note._deleted || note._perm_deleted) return;
        if (note.topic_id && note.topic_id !== '未分類') topicsMap[note.topic_id] = true;
        else hasUnclassified = true;
      });
      var topicNames = Object.keys(topicsMap).sort();
      if (hasUnclassified) {
        topicNames.unshift('未分類');
      }
      if (!topicNames.length) {
        container.innerHTML = '<div style="padding:12px;color:#888;font-size:.82rem;">尚無自訂主題</div>';
        return;
      }
      topicNames.forEach(function(tn){
        var cardsInTopic = Object.keys(USER_CONCEPT_NOTES).filter(function(k){
          if (!k.startsWith(customPrefix)) return false;
          var note = USER_CONCEPT_NOTES[k];
          if (note._deleted || note._perm_deleted) return false;
          if (tn === '未分類') return !note.topic_id || note.topic_id === '未分類';
          return note.topic_id === tn;
        });
        var total = cardsInTopic.length;
        var item = mk('div', 'topic-item' + (S.topic === tn ? ' active' : ''));
        var nameEl = mk('span', 'topic-item-name', escHtml(tn));
        var prog   = mk('span', 'topic-prog done', total + ' 卡');
        item.appendChild(nameEl);
        item.appendChild(prog);
        item.addEventListener('click', function(){ selectTopic(tn); });
        container.appendChild(item);
      });
    } else {
      // 預設模式：顯示系統主題與答題進度
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
  }

  function topicsForSubject(lsId) {
    return Object.keys(window.QDB.topics).filter(function(tid){
      return window.QDB.topics[tid].law_subject === lsId;
    }).sort(function(a, b){
      return (window.QDB.topics[b].importance||0) - (window.QDB.topics[a].importance||0);
    });
  }

  function selectTopic(tid) {
    S.topic = (S.topic === tid) ? null : tid;  // 再點同一個主題就取消
    // 選了主題就自動切到「依主題」；取消主題不強制切換
    if (S.topic) {
      var radioTopic = $q('input[name="qorder"][value="by_topic"]');
      if (radioTopic) radioTopic.checked = true;
    }
    renderTopicList();
    updateTopicChip();
    if (S.mode === 'concept') renderConceptArea();
    else startQuiz();
  }

  function updateTopicChip() {
    var hint = $q('#topic-sel-hint');
    if (hint) {
      if (!S.lawSubject) {
        hint.classList.add('hidden');
      } else if (S.topic && window.QDB.topics[S.topic]) {
        hint.textContent = '📌 已選主題，再按一次可取消';
        hint.classList.remove('hidden');
      } else {
        hint.textContent = '尚未選擇主題，將練習本科全部題目';
        hint.classList.remove('hidden');
      }
    }
    $a('#topic-chips-bar .tc-chip').forEach(function(c){
      c.classList.toggle('active', c.dataset.tid === S.topic);
    });
  }

  function renderTopicChipsBar() {
    var bar = $q('#topic-chips-bar');
    var row = $q('#topic-chips-row');
    if (!bar || !row) return;
    bar.innerHTML = '';
    if (!S.lawSubject) { row.style.display = 'none'; return; }
    var tids = topicsForSubject(S.lawSubject);
    if (!tids.length) { row.style.display = 'none'; return; }
    tids.forEach(function(tid){
      var t = window.QDB.topics[tid];
      var chip = mk('button', 'tc-chip' + (S.topic === tid ? ' active' : ''),
        escHtml(t.short_name || t.name.split('｜').pop()));
      chip.dataset.tid = tid;
      chip.addEventListener('click', function(){
        // 篩選用：只更新主題篩選，不自動開始練習（讓使用者按「開始練習」）
        S.topic = (S.topic === tid) ? null : tid;
        if (S.topic) {
          var rb = $q('input[name="qorder"][value="by_topic"]');
          if (rb) rb.checked = true;
        }
        renderTopicList();
        updateTopicChip();
        renderTopicChipsBar();
      });
      bar.appendChild(chip);
    });
    row.style.display = '';
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
        setDesktopMode(btn.dataset.mode);
        updateMbarActive();
      });
    });
  }

  // 桌機模式切換（concept / quiz / audio 三者擇一）
  function setDesktopMode(mode) {
    S.mode = mode;
    renderTopicList(); // 切換模式時，同步重新渲染側邊欄主題列表
    if (mode === 'audio') {
      hide('panel-concept'); hide('panel-quiz'); show('panel-audio');
      if (!AUD.inited) {
        initAudioView();
      } else {
        var aDef = $q('#aud-dm-default');
        var aBlk = $q('#aud-dm-blank');
        if (aDef) aDef.classList.toggle('dm-btn-active', S.dataMode === 'default');
        if (aBlk) aBlk.classList.toggle('dm-btn-active', S.dataMode === 'blank');
      }
      rebuildAudio();
    } else {
      audStop();
      hide('panel-audio');
      if (mode === 'concept') {
        show('panel-concept'); hide('panel-quiz');
        renderConceptArea();
      } else {
        hide('panel-concept'); show('panel-quiz');
      }
    }
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
      area.innerHTML = '<div class="placeholder">請先點選上方科目欄選擇科目</div>';
      return;
    }

    // ── 資料模式切換列 ──────────────────────────────
    var modeRow = mk('div', 'data-mode-row');
    var isBlank = (S.dataMode === 'blank');
    var dmLabel = mk('span', 'dm-label', '📂 資料模式：');
    var dmBtnDefault = mk('button', 'dm-btn' + (!isBlank ? ' dm-btn-active' : ''), '📚 預設資料');
    var dmBtnBlank   = mk('button', 'dm-btn' + (isBlank  ? ' dm-btn-active' : ''), '✏️ 自主筆記');
    dmBtnDefault.title = '顯示系統預設概念卡（可繼續自由新增自訂卡片）';
    dmBtnBlank.title   = '隱藏所有預設卡，只顯示在「自主筆記」模式下新增的概念卡';
    dmBtnDefault.addEventListener('click', function() {
      if (S.dataMode === 'default') return;
      S.dataMode = 'default'; S.topic = null; saveLocalDataMode();
      renderTopicList(); // 切換時同步更新左側欄主題
      renderConceptArea();
      rebuildAudio();
    });
    dmBtnBlank.addEventListener('click', function() {
      if (S.dataMode === 'blank') return;
      S.dataMode = 'blank'; S.topic = null; saveLocalDataMode();
      renderTopicList(); // 切換時同步更新左側欄主題
      renderConceptArea();
      rebuildAudio();
    });
    modeRow.appendChild(dmLabel);
    modeRow.appendChild(dmBtnDefault);
    modeRow.appendChild(dmBtnBlank);
    hdr.appendChild(modeRow);

    // ── 主題 chip 導覽列 ────────────────────────
    var topicIds = topicsForSubject(S.lawSubject);
    if (nav) {
      nav.innerHTML = '';
      if (isBlank) {
        // 自主筆記模式：顯示「全部」chip + 使用者在此科目自己新增的自訂主題 chip + 「未分類」chip
        var customPrefix = S.lawSubject + ':blank_custom_';
        var topicsMap = {};
        var hasUnclassified = false;
        Object.keys(USER_CONCEPT_NOTES).forEach(function(k) {
          if (!k.startsWith(customPrefix)) return;
          var note = USER_CONCEPT_NOTES[k];
          if (note._deleted || note._perm_deleted) return;
          if (note.topic_id && note.topic_id !== '未分類') topicsMap[note.topic_id] = true;
          else hasUnclassified = true;
        });
        var topicNames = Object.keys(topicsMap).sort();
        if (hasUnclassified) {
          topicNames.unshift('未分類');
        }

        var allChip = mk('button', 'ctopic-chip' + (!S.topic ? ' active' : ''), '全部');
        allChip.addEventListener('click', function(){
          S.topic = null;
          renderConceptArea();
        });
        nav.appendChild(allChip);

        topicNames.forEach(function(tn){
          var chip = mk('button',
            'ctopic-chip imp-chip-medium' + (S.topic === tn ? ' active' : ''),
            escHtml(tn));
          chip.addEventListener('click', function(){
            S.topic = tn;
            renderConceptArea();
            // 同步側欄
            $a('.topic-item').forEach(function(item){
              item.classList.toggle('active', item.querySelector('.topic-item-name').textContent === tn);
            });
          });
          nav.appendChild(chip);
        });
      } else {
        // 預設模式：顯示「全部」chip + 各預設主題 chip
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
    }

    // ── 標題 ───────────────────────────────────
    var titleText = S.lawSubject.replace(/^custom:/, '');
    if (S.topic && window.QDB.topics[S.topic]) titleText += ' ▸ ' + window.QDB.topics[S.topic].name.split('｜').pop();
    var h2El = mk('h2', '', escHtml(titleText) + ' 概念複習');
    hdr.appendChild(h2El);

    // ── 取得概念卡 ──────────────────────────────
    var targetTopics;
    if (isBlank) {
      if (S.topic) {
        targetTopics = [S.topic];
      } else {
        var customPrefix = S.lawSubject + ':blank_custom_';
        var topicsMap = {};
        var hasUnclassified = false;
        Object.keys(USER_CONCEPT_NOTES).forEach(function(k) {
          if (!k.startsWith(customPrefix)) return;
          var note = USER_CONCEPT_NOTES[k];
          if (note._deleted || note._perm_deleted) return;
          if (note.topic_id && note.topic_id !== '未分類') topicsMap[note.topic_id] = true;
          else hasUnclassified = true;
        });
        targetTopics = Object.keys(topicsMap).sort();
        if (hasUnclassified) {
          targetTopics.unshift('未分類');
        }
      }
    } else {
      targetTopics = S.topic ? [S.topic] : topicIds;
    }

    area.innerHTML = '';
    var isCustomSubject = !topicIds.length;

    if (isCustomSubject) {
      // ── 自訂科目：只顯示使用者自訂概念卡 ──────
      var customPrefix = S.lawSubject + ':';
      Object.keys(USER_CONCEPT_NOTES)
        .filter(function(k){ return k.startsWith(customPrefix); })
        .forEach(function(noteKey){
          var note = USER_CONCEPT_NOTES[noteKey];
          if (note._deleted || note._perm_deleted) return;
          area.appendChild(buildConceptCard({
            id: noteKey, topic: '', law_subject: S.lawSubject,
            front: note.front, back: note.back, importance: 'medium', tags: []
          }, noteKey, true));
        });
    } else {
      // ── 一般科目：顯示各主題的概念卡 ──────────
      if (!isBlank) {
        // 預設模式：顯示系統卡
        targetTopics.forEach(function(tid){
          var t = window.QDB.topics[tid];
          // 1. 手動卡片（優先）
          var manual = (window.FLASHCARDS || []).filter(function(c){ return c.topic === tid; });
          if (manual.length) {
            manual.forEach(function(c){
              var note = USER_CONCEPT_NOTES[c.id];
              if (note && (note._deleted || note._perm_deleted)) return;
              var displayCard = note && note.front ? Object.assign({}, c, { front: note.front, back: note.back }) : c;
              area.appendChild(buildConceptCard(displayCard, c.id, false));
            });
          }
          // 2. 考點彙整卡（從真實考題提取，一律顯示）
          var gen = (window.GENERATED_FLASHCARDS || []).filter(function(c){ return c.topic === tid; });
          if (gen.length) {
            gen.forEach(function(c){
              var note = USER_CONCEPT_NOTES[c.id];
              if (note && (note._deleted || note._perm_deleted)) return;
              var displayCard = note && note.front ? Object.assign({}, c, { front: note.front, back: note.back }) : c;
              area.appendChild(buildConceptCard(displayCard, c.id, false));
            });
          } else if (!manual.length) {
            var autoC = autoCard(tid, t);
            var note  = USER_CONCEPT_NOTES[autoC.id];
            if (!(note && (note._deleted || note._perm_deleted))) {
              var displayCard = note && note.front ? Object.assign({}, autoC, { front: note.front, back: note.back }) : autoC;
              area.appendChild(buildConceptCard(displayCard, autoC.id, false));
            }
          }

          // 3. 使用者手動新增且屬於目前主題的自訂卡（在主題分區下顯示）
          var subjPrefix = isBlank ? (S.lawSubject + ':blank_custom_') : (S.lawSubject + ':custom_');
          Object.keys(USER_CONCEPT_NOTES)
            .filter(function(k){
              if (!k.startsWith(subjPrefix)) return false;
              var note = USER_CONCEPT_NOTES[k];
              if (note._deleted || note._perm_deleted) return false;
              return note.topic_id === tid;
            })
            .forEach(function(noteKey){
              var note = USER_CONCEPT_NOTES[noteKey];
              area.appendChild(buildConceptCard({
                id: noteKey, topic: tid, law_subject: S.lawSubject,
                front: note.front, back: note.back, importance: 'medium', tags: []
              }, noteKey, true));
            });
        });
      } else {
        // 自主筆記模式下：如果篩選特定主題，顯示該主題的自訂卡
        targetTopics.forEach(function(tid){
          var subjPrefix = isBlank ? (S.lawSubject + ':blank_custom_') : (S.lawSubject + ':custom_');
          Object.keys(USER_CONCEPT_NOTES)
            .filter(function(k){
              if (!k.startsWith(subjPrefix)) return false;
              var note = USER_CONCEPT_NOTES[k];
              if (note._deleted || note._perm_deleted) return false;
              if (tid === '未分類') return !note.topic_id || note.topic_id === '未分類';
              return note.topic_id === tid;
            })
            .forEach(function(noteKey){
              var note = USER_CONCEPT_NOTES[noteKey];
              area.appendChild(buildConceptCard({
                id: noteKey, topic: tid, law_subject: S.lawSubject,
                front: note.front, back: note.back, importance: 'medium', tags: []
              }, noteKey, true));
            });
        });
      }

      // ── 使用者在此科目手動新增的自訂卡（未歸類主題的卡片，僅在「全部」視角的最下方顯示）─────────
      if (!isBlank && !S.topic) {
        var subjPrefix = isBlank ? (S.lawSubject + ':blank_custom_') : (S.lawSubject + ':custom_');
        Object.keys(USER_CONCEPT_NOTES)
          .filter(function(k){
            if (!k.startsWith(subjPrefix)) return false;
            var note = USER_CONCEPT_NOTES[k];
            if (note._deleted || note._perm_deleted) return false;
            return !note.topic_id; // 沒有歸類主題的
          })
          .forEach(function(noteKey){
            var note = USER_CONCEPT_NOTES[noteKey];
            area.appendChild(buildConceptCard({
              id: noteKey, topic: '', law_subject: S.lawSubject,
              front: note.front, back: note.back, importance: 'medium', tags: []
            }, noteKey, true));
          });
      }
    }

    // ── 「＋ 新增自訂概念卡」按鈕（不論是否選取主題皆顯示，若有選取則預設為該主題） ─────────────────
    var addCardBtn = mk('button', 'concept-add-card-btn', '＋ 新增自訂概念卡');
    addCardBtn.addEventListener('click', function(){
      var isBlank = (S.dataMode === 'blank');
      var prefix = isCustomSubject ? (S.lawSubject + ':') : (isBlank ? (S.lawSubject + ':blank_custom_') : (S.lawSubject + ':custom_'));
      var defTopic = S.topic || '';
      openConceptNoteEditor(prefix + Date.now(), S.lawSubject, defTopic, '', '', true);
    });
    area.appendChild(addCardBtn);

    if (S.topic && !area.querySelector('.concept-card'))
      area.innerHTML = '<div class="placeholder">此主題尚無概念卡</div>';

    // ── 垃圾桶區（已刪除的概念卡）───────────────────
    renderConceptTrash(area);
  }

  function renderConceptTrash(area) {
    // 蒐集此科目下所有 _deleted 的卡
    var isBlank = (S.dataMode === 'blank');
    var subjPrefix = isBlank ? (S.lawSubject + ':blank_custom_') : (S.lawSubject + ':custom_');
    var deletedKeys = Object.keys(USER_CONCEPT_NOTES).filter(function(k){
      var n = USER_CONCEPT_NOTES[k];
      if (!n._deleted) return false;
      return k.startsWith(subjPrefix);
    });
    
    if (!isBlank) {
      // 預設模式：另外加上被刪除的系統卡
      var allSysCards = (window.FLASHCARDS || []).concat(window.GENERATED_FLASHCARDS || []);
      allSysCards.forEach(function(c){
        if (c.law_subject !== S.lawSubject) return;
        var n = USER_CONCEPT_NOTES[c.id];
        if (n && n._deleted && deletedKeys.indexOf(c.id) < 0) deletedKeys.push(c.id);
      });
    }

    if (!deletedKeys.length) return;

    var sec = mk('div', 'trash-section');
    var hdr = mk('div', 'trash-header');
    hdr.innerHTML =
      '<span class="trash-header-title">🗑 垃圾桶（' + deletedKeys.length + ' 張）</span>' +
      '<span class="trash-header-toggle">▼</span>';
    var body = mk('div', 'trash-body hidden');
    sec.appendChild(hdr);
    sec.appendChild(body);

    hdr.addEventListener('click', function(){
      body.classList.toggle('hidden');
      hdr.querySelector('.trash-header-toggle').textContent = body.classList.contains('hidden') ? '▼' : '▲';
    });

    deletedKeys.forEach(function(key){
      var n = USER_CONCEPT_NOTES[key];
      // 取得卡片標題
      var label = n.front || (function(){
        var sys = allSysCards.find(function(c){ return c.id === key; });
        return sys ? sys.front : key;
      })();
      var isCustom = !!(n.subject && key.indexOf('custom_') > -1) || !allSysCards.find(function(c){ return c.id === key; });

      var item = mk('div', 'trash-item');
      var labelEl = mk('span', 'trash-item-label', '📋 ' + escHtml(label));
      var restoreBtn = mk('button', 'trash-restore-btn', '↩ 恢復');
      var permDelBtn = mk('button', 'trash-perm-del-btn', '🗑 永久刪除');
      item.appendChild(labelEl);
      item.appendChild(restoreBtn);
      item.appendChild(permDelBtn);
      body.appendChild(item);

      restoreBtn.addEventListener('click', function(){
        var n = USER_CONCEPT_NOTES[key];
        if (isCustom && n && n.front) {
          delete n._deleted;
          saveConceptNotesLocal();
          syncConceptNote(key, n);
        } else {
          delete USER_CONCEPT_NOTES[key];
          saveConceptNotesLocal();
          deleteConceptNoteServer(key);
        }
        renderConceptArea();
        renderTopicList();
        rebuildAudio();
      });
      permDelBtn.addEventListener('click', function(){
        if (!confirm('確定永久刪除「' + label + '」？此操作無法恢復。')) return;
        if (isCustom) {
          delete USER_CONCEPT_NOTES[key];
          deleteConceptNoteServer(key);
        } else {
          USER_CONCEPT_NOTES[key] = { _perm_deleted: true };
          syncConceptNote(key, { _perm_deleted: true });
        }
        saveConceptNotesLocal();
        renderConceptArea();
        renderTopicList();
        rebuildAudio();
      });
    });
    area.appendChild(sec);
  }

  function autoCard(tid, t) {
    var qsInTopic = window.QDB.questions.filter(function(q){ return q.topic === tid; });
    var total = qsInTopic.length;
    var years = [...new Set(qsInTopic.map(function(q){ return q.year; }))].sort().reverse();
    var kws = (t.kw || []);
    var backLines = [];
    if (kws.length) backLines.push('【核心概念關鍵字】\n' + kws.map(function(k){ return '• ' + k; }).join('\n'));
    backLines.push('【歷年出題統計】共 ' + total + ' 題（' + (years.slice(0,3).join('、') + (years.length>3 ? '…等' : '') + '年') + '）');
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

  function buildConceptCard(c, editKey, isCustomCard) {
    var isReviewed = !!S.reviewed[c.id];
    var isImportant = !!S.important[c.id];
    var isForget = !!S.forget[c.id];
    var impCls = 'imp-' + (c.importance || 'medium');
    var isGen = c.id && c.id.startsWith('gen_');
    var card = mk('div', 'concept-card' + (isGen ? ' gen-card' : '') + (isCustomCard ? ' custom-card' : ''));
    var backHtml = escHtml(c.back).replace(/\n/g, '<br>');

    var headFlagsHtml =
      '<div class="cc-head-flags">' +
        '<span class="cc-flag-btn flag-reviewed' + (isReviewed ? ' active' : '') + '" data-cid="' + escHtml(c.id) + '" title="已複習">✓ 複習</span>' +
        '<span class="cc-flag-btn flag-important' + (isImportant ? ' active' : '') + '" data-cid="' + escHtml(c.id) + '" title="重點">⭐ 重點</span>' +
        '<span class="cc-flag-btn flag-forget' + (isForget ? ' active' : '') + '" data-cid="' + escHtml(c.id) + '" title="易忘">⚠️ 易忘</span>' +
      '</div>';

    card.innerHTML =
      '<div class="concept-card-head">' +
        '<span class="cc-imp-dot ' + impCls + '"></span>' +
        '<span class="cc-title">' + escHtml(c.front) + '</span>' +
        headFlagsHtml +
        (editKey ? '<button class="cc-edit-btn" title="編輯此卡">✏️</button>' : '') +
        (editKey ? '<button class="cc-del-btn" title="刪除此卡">🗑</button>' : '') +
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

    card.querySelector('.concept-card-head').addEventListener('click', function(e){
      if (e.target.classList.contains('cc-edit-btn')) return;
      if (e.target.classList.contains('cc-del-btn')) return;
      if (e.target.classList.contains('cc-flag-btn')) return;
      card.classList.toggle('expanded');
    });

    $a('.cc-flag-btn', card).forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.stopPropagation();
        var cid = btn.dataset.cid;
        if (btn.classList.contains('flag-reviewed')) {
          S.reviewed[cid] = !S.reviewed[cid];
          saveLocalProgress(); syncToServer();
          var active = !!S.reviewed[cid];
          btn.classList.toggle('active', active);
          var bBtn = card.querySelector('.cc-reviewed-btn');
          if (bBtn) {
            bBtn.textContent = active ? '✓ 已複習' : '標記為已複習';
            bBtn.classList.toggle('marked', active);
          }
          updateStatBadge();
        } else if (btn.classList.contains('flag-important')) {
          S.important[cid] = !S.important[cid];
          localStorage.setItem('concept_important', JSON.stringify(S.important));
          syncCustomSubjects();
          btn.classList.toggle('active', !!S.important[cid]);
        } else if (btn.classList.contains('flag-forget')) {
          S.forget[cid] = !S.forget[cid];
          localStorage.setItem('concept_forget', JSON.stringify(S.forget));
          syncCustomSubjects();
          btn.classList.toggle('active', !!S.forget[cid]);
        }
      });
    });

    card.querySelector('.cc-reviewed-btn').addEventListener('click', function(e){
      e.stopPropagation();
      var btn = e.currentTarget;
      var cid = btn.dataset.cid;
      S.reviewed[cid] = !S.reviewed[cid];
      saveLocalProgress(); syncToServer();
      var isNowReviewed = !!S.reviewed[cid];
      btn.textContent = isNowReviewed ? '✓ 已複習' : '標記為已複習';
      btn.classList.toggle('marked', isNowReviewed);
      var headBtn = card.querySelector('.cc-flag-btn.flag-reviewed');
      if (headBtn) headBtn.classList.toggle('active', isNowReviewed);
      updateStatBadge();
    });
    if (editKey) {
      (function(capturedKey, capturedC, capturedIsCustom){
        var editBtn = card.querySelector('.cc-edit-btn');
        if (editBtn) {
          editBtn.addEventListener('click', function(e){
            e.stopPropagation();
            var existing = USER_CONCEPT_NOTES[capturedKey];
            openConceptNoteEditor(
              capturedKey,
              capturedC.law_subject || S.lawSubject,
              capturedC.topic || '',
              existing ? existing.front : capturedC.front,
              existing ? existing.back  : capturedC.back,
              capturedIsCustom
            );
          });
        }
        var delBtn = card.querySelector('.cc-del-btn');
        if (delBtn) {
          delBtn.addEventListener('click', function(e){
            e.stopPropagation();
            var msg = capturedIsCustom
              ? '確定刪除這張自訂概念卡？（可至下方垃圾桶恢復）'
              : '確定從畫面刪除這張卡片？（可至編輯器重置恢復）';
            if (!confirm(msg)) return;
            if (capturedIsCustom) {
              var existing = USER_CONCEPT_NOTES[capturedKey] || { front: capturedC.front, back: capturedC.back, subject: capturedC.law_subject || S.lawSubject };
              USER_CONCEPT_NOTES[capturedKey] = Object.assign({}, existing, { _deleted: true });
              syncConceptNote(capturedKey, USER_CONCEPT_NOTES[capturedKey]);
            } else {
              USER_CONCEPT_NOTES[capturedKey] = { _deleted: true };
              syncConceptNote(capturedKey, { _deleted: true });
            }
            saveConceptNotesLocal();
            renderConceptArea();
            renderTopicList();
            rebuildAudio();
          });
        }
      })(editKey, c, isCustomCard);
    }
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
    // 動態建立篩選按鈕
    var filterBar = $q('.filter-bar');
    if (filterBar) {
      var filterRow = mk('div', 'filter-row');
      filterRow.innerHTML = '<span class="filter-label">🔖 篩選</span>';
      [{ v:'all', t:'📋 全部' }, { v:'wrong', t:'❌ 錯題' }, { v:'bookmarked', t:'⭐ 收藏' }].forEach(function(f){
        var btn = mk('button', 'qfilter-btn' + (S.quizFilter === f.v ? ' active' : ''), f.t);
        btn.dataset.filter = f.v;
        btn.addEventListener('click', function(){
          S.quizFilter = f.v;
          $a('.qfilter-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.filter === S.quizFilter); });
          if (S.lawSubject) startQuiz();
        });
        filterRow.appendChild(btn);
      });
      var lastRow = $a('.filter-row', filterBar).pop();
      if (lastRow) filterBar.insertBefore(filterRow, lastRow);
      else filterBar.appendChild(filterRow);
    }
    $q('#btn-start').addEventListener('click', startQuiz);
    $a('input[name="qorder"]').forEach(function(radio){
      radio.addEventListener('change', function(){
        if (radio.value === 'by_seq' && S.topic) {
          S.topic = null;
          renderTopicList();
          updateTopicChip();
        }
      });
    });
    $q('#q-prev').addEventListener('click', function(){ goQuestion(-1); });
    $q('#q-next').addEventListener('click', function(){ goQuestion(1); });
  }

  function startQuiz() {
    if (!S.lawSubject) {
      $q('#quiz-area').innerHTML = '<div class="placeholder">請先點選上方科目欄選擇科目</div>';
      return;
    }
    var currentSubject = S.lawSubject;
    var years = $a('#year-checks input:checked').map(function(c){ return parseInt(c.value); });
    var questions = window.QDB.questions.filter(function(q){
      if (!q.law_subject || q.law_subject !== currentSubject) return false;
      if (!years.includes(q.year)) return false;
      if (S.topic && q.topic !== S.topic) return false;
      return true;
    });
    // ── 第二層篩選：錯題 / 受藏方式
    if (S.quizFilter === 'wrong') {
      questions = questions.filter(function(q){
        return S.answers[q.id] && !S.answers[q.id].correct;
      });
    } else if (S.quizFilter === 'bookmarked') {
      questions = questions.filter(function(q){ return !!S.bookmarks[q.id]; });
    }
    if (!questions.length) {
      $q('#quiz-area').innerHTML = '<div class="placeholder">沒有符合條件的題目，請調整篩選條件</div>';
      return;
    }
    var order = $q('input[name="qorder"]:checked');
    var orderVal = order ? order.value : 'by_topic';
    if (orderVal === 'by_topic') {
      questions = questions.slice().sort(function(a, b){
        var ia = window.QDB.topics[a.topic] ? (window.QDB.topics[a.topic].importance||0) : 0;
        var ib = window.QDB.topics[b.topic] ? (window.QDB.topics[b.topic].importance||0) : 0;
        if (ib !== ia) return ib - ia;
        if (a.topic !== b.topic) return a.topic < b.topic ? -1 : 1;
        return b.year - a.year;
      });
    } else {
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

    // 標題：顯示原卷年份與題號
    var isBookmarked = !!S.bookmarks[q.id];
    card.innerHTML =
      '<div class="q-top-bar">' +
        '<span class="q-num-label">' + q.year + '年 第 ' + q.num + ' 題</span>' +
        '<button class="q-bookmark-btn' + (isBookmarked ? ' bookmarked' : '') + '" title="收藏此題">' + (isBookmarked ? '★' : '☆') + '<span class="q-bm-text">收藏</span></button>' +
      '</div>' +
      '<div class="q-meta">' + escHtml(q.law_subject) + (topicName ? ' ／ ' + escHtml(topicName) : '') + '</div>' +
      '<div class="q-stem">' + escHtml(q.question) + '</div>' +
      '<div class="opts"></div>';

    // 書籤切換
    card.querySelector('.q-bookmark-btn').addEventListener('click', function(e){
      e.stopPropagation();
      S.bookmarks[q.id] = !S.bookmarks[q.id];
      if (!S.bookmarks[q.id]) delete S.bookmarks[q.id];
      saveLocalBookmarks();
      syncBookmarkToServer(q.id);
      var bBtn = e.currentTarget;
      var bOn  = !!S.bookmarks[q.id];
      bBtn.innerHTML = (bOn ? '★' : '☆') + '<span class="q-bm-text">收藏</span>';
      bBtn.classList.toggle('bookmarked', bOn);
    });

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

    if (answered) showExplanation(card, q);
    area.appendChild(card);

    // ── 題目筆記區 ───────────────────────────────
    var noteArea = mk('div', 'q-note-area');
    var hasNote  = !!(S.qnotes[q.id] && S.qnotes[q.id].trim());
    var noteHdr  = mk('div', 'q-note-header');
    noteHdr.innerHTML =
      '<span>📝 我的筆記</span>' +
      (hasNote ? '<span class="q-note-indicator">已有筆記</span>' : '') +
      '<button class="q-note-toggle">' + (hasNote ? '收起' : '展開') + '</button>';
    var noteBody = mk('div', 'q-note-body' + (hasNote ? '' : ' hidden'));
    noteBody.innerHTML =
      '<textarea class="q-note-textarea" rows="4" placeholder="輸入你對這題的筆記…">' +
        escHtml(S.qnotes[q.id] || '') +
      '</textarea>' +
      '<div class="q-note-actions">' +
        '<button class="ai-refine-btn q-note-ai-btn">✨ AI 整理</button>' +
        '<span class="ai-refine-hint q-note-ai-hint"></span>' +
        '<button class="btn-outline q-note-cancel">取消</button>' +
        '<button class="btn-primary q-note-save">儲存筆記</button>' +
      '</div>';
    noteArea.appendChild(noteHdr);
    noteArea.appendChild(noteBody);

    noteHdr.querySelector('.q-note-toggle').addEventListener('click', function(){
      var open = !noteBody.classList.contains('hidden');
      noteBody.classList.toggle('hidden', open);
      this.textContent = open ? '展開' : '收起';
    });
    noteBody.querySelector('.q-note-cancel').addEventListener('click', function(){
      noteBody.querySelector('.q-note-textarea').value = S.qnotes[q.id] || '';
      var preview = noteBody.querySelector('.ai-preview-box');
      if (preview) preview.remove();
      noteBody.classList.add('hidden');
      noteHdr.querySelector('.q-note-toggle').textContent = '展開';
    });
    noteBody.querySelector('.q-note-ai-btn').addEventListener('click', function(){
      aiRefineText(noteBody.querySelector('.q-note-textarea'), 'question_note', noteBody.querySelector('.q-note-ai-hint'));
    });
    noteBody.querySelector('.q-note-save').addEventListener('click', function(){
      var text = noteBody.querySelector('.q-note-textarea').value.trim();
      S.qnotes[q.id] = text;
      saveLocalQnotes();
      syncQnote(q.id, text);
      var ind = noteHdr.querySelector('.q-note-indicator');
      if (text && !ind) {
        var newInd = mk('span', 'q-note-indicator', '已有筆記');
        noteHdr.insertBefore(newInd, noteHdr.querySelector('.q-note-toggle'));
      } else if (!text && ind) { ind.remove(); }
      var saveMsg = mk('span', 'ai-refine-hint', '✓ 已儲存');
      saveMsg.style.color = '#2a9d8f';
      var actRow = noteBody.querySelector('.q-note-actions');
      var oldMsg = actRow.querySelector('.save-msg');
      if (oldMsg) oldMsg.remove();
      saveMsg.classList.add('save-msg');
      actRow.appendChild(saveMsg);
      setTimeout(function(){ if (saveMsg.parentNode) saveMsg.remove(); }, 1500);
    });
    area.appendChild(noteArea);

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
    // 清除舊的詳解與按鈕
    var old = card.querySelector('.expl-box');
    if (old) old.remove();
    var oldBtn = card.querySelector('.btn-retry');
    if (oldBtn) oldBtn.remove();
    // 每次顯示詳解都附上重新選擇按鈕
    var retryBtn = mk('button', 'btn-retry', '↺ 清除本題記錄，重新選擇');
    retryBtn.addEventListener('click', function(){
      delete S.answers[q.id];
      saveLocalProgress(); syncToServer();
      renderQuestion();
      renderTopicList(); updateStatBadge();
    });
    card.appendChild(retryBtn);
    card.appendChild(buildExplBox(q));
  }

  function buildExplBox(q) {
    var box      = mk('div', 'expl-box');
    var answered = S.answers[q.id];
    var correct  = q.answer;
    // 詳解資料為延遲載入：若尚未載入完成，載好後自動重新渲染本題
    if (!explReady()) {
      ensureExpl(function () {
        if (S.mode === 'quiz' && S.pool[S.idx] === q) renderQuestion();
      });
    }
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
    } else if (!explReady()) {
      var cb = mk('div', 'expl-concept');
      cb.innerHTML = '<div class="expl-concept-label">🔑 核心概念</div>📥 詳解載入中，請稍候…';
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
      '<div class="ai-chat-label">🤖 AI 追問</div>' +
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
        ansDiv.textContent = 'AI 連線失敗，請稍後再試';
      }).finally(function(){ sendBtn.disabled=false; sendBtn.textContent='送出'; });
    });
    return box;
  }

  /* ══════════════════════════════════════════════
     AI 整理文字（共用）
  ══════════════════════════════════════════════ */
  function aiRefineText(ta, mode, hintEl) {
    var text = ta.value.trim();
    if (!text) {
      if (hintEl) { hintEl.textContent = '請先輸入內容'; hintEl.style.color = '#e55'; }
      return;
    }
    // 移除已存在的預覽框
    var container = hintEl ? hintEl.parentNode : ta.parentNode;
    var old = container.parentNode && container.parentNode.querySelector('.ai-preview-box');
    if (old) old.remove();

    if (hintEl) { hintEl.textContent = 'AI 整理中…'; hintEl.style.color = '#888'; }
    fetch(API + '/api/ai_refine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: text, mode: mode })
    }).then(function(r){ return r.json(); })
      .then(function(d){
        if (d.result) {
          if (hintEl) { hintEl.textContent = ''; }
          showAiPreview(ta, d.result, hintEl, d.truncated);
        } else {
          if (hintEl) { hintEl.textContent = d.error || 'AI 整理失敗'; hintEl.style.color = '#e55'; }
        }
      }).catch(function(){
        if (hintEl) { hintEl.textContent = 'AI 連線失敗'; hintEl.style.color = '#e55'; }
      });
  }

  function showAiPreview(ta, refinedText, hintEl, truncated) {
    var insertAfter = hintEl ? hintEl.parentNode : ta;
    var preview = mk('div', 'ai-preview-box');
    var previewTa = mk('textarea', 'ai-preview-textarea');
    previewTa.value = refinedText;
    var label = mk('div', 'ai-preview-label', '✨ AI 整理結果（可再編輯）');
    preview.appendChild(label);
    if (truncated) {
      var warn = mk('div', 'ai-preview-warn', '⚠️ 內容較長，AI 可能未整理完，建議分段處理');
      warn.style.cssText = 'font-size:.78rem;color:#b45309;background:#fef3c7;padding:6px 10px;border-radius:6px;';
      preview.appendChild(warn);
    }
    var actions = mk('div', 'ai-preview-actions');
    var confirmBtn = mk('button', 'ai-preview-confirm', '✅ 確認套用');
    var cancelBtn  = mk('button', 'ai-preview-cancel', '✗ 取消');
    actions.appendChild(confirmBtn);
    actions.appendChild(cancelBtn);
    preview.appendChild(previewTa);
    preview.appendChild(actions);
    insertAfter.insertAdjacentElement('afterend', preview);

    confirmBtn.addEventListener('click', function(){
      ta.value = previewTa.value;
      preview.remove();
      if (hintEl) { hintEl.textContent = '✓ 已套用'; hintEl.style.color = '#2a9d8f'; }
    });
    cancelBtn.addEventListener('click', function(){
      preview.remove();
      if (hintEl) hintEl.textContent = '';
    });
  }

  /* ══════════════════════════════════════════════
     聽讀自訂筆記
  ══════════════════════════════════════════════ */
  var USER_AUDIO_NOTES = {};   // noteKey -> {title, points:[]}

  function loadAudioNotes() {
    try { USER_AUDIO_NOTES = JSON.parse(localStorage.getItem('audio_user_notes') || '{}'); } catch(e) {}
  }

  function saveAudioNotesLocal() {
    localStorage.setItem('audio_user_notes', JSON.stringify(USER_AUDIO_NOTES));
  }

  function syncAudioNote(noteKey, titleStr, pointsArr) {
    if (!S.token) return;
    fetch(API + '/api/audio_notes', {
      method: 'POST', headers: apiHeaders(),
      body: JSON.stringify({ note_key: noteKey, title: titleStr, points: pointsArr })
    }).catch(function(){});
  }

  function loadServerAudioNotes() {
    if (!S.token) return;
    fetch(API + '/api/audio_notes', { headers: apiHeaders() })
      .then(function(r){ return r.json(); })
      .then(function(d){
        Object.assign(USER_AUDIO_NOTES, d);
        saveAudioNotesLocal();
        if (AUD.inited && S.lawSubject) {
          buildSegments(S.lawSubject);
          renderAudSegList();
          _audUpdateBtn();
        }
      }).catch(function(){});
  }

  function deleteAudioNote(noteKey) {
    delete USER_AUDIO_NOTES[noteKey];
    saveAudioNotesLocal();
    if (S.token) {
      fetch(API + '/api/audio_notes/' + encodeURIComponent(noteKey), {
        method: 'DELETE', headers: apiHeaders()
      }).catch(function(){});
    }
  }

  /* ── 筆記編輯器 ─────────────────────────────── */
  function openAudioNoteEditor(noteKey, titleStr, isCustom) {
    var existing = USER_AUDIO_NOTES[noteKey];
    var prefillPts = [];
    if (existing && existing.points && existing.points.length) {
      prefillPts = existing.points;
    } else if (window.AUDIO_SCRIPTS && window.AUDIO_SCRIPTS[noteKey]) {
      prefillPts = window.AUDIO_SCRIPTS[noteKey].points;
    } else {
      var seg = AUD.segs.find(function(x) { return x.noteKey === noteKey; });
      if (seg && seg.sentences && seg.sentences.length > 1) {
        prefillPts = seg.sentences.slice(1);
      }
    }
    var pointsText = prefillPts.join('\n');

    var overlay = mk('div', 'aud-editor-overlay');
    var box     = mk('div', 'aud-editor-box');
    box.innerHTML =
      '<div class="aud-editor-title">' +
        (isCustom ? '✏️ 自訂段落' : '✏️ 補充筆記：' + escHtml(titleStr)) +
      '</div>' +
      (isCustom ?
        '<input class="aud-editor-input" id="aud-editor-seg-title" placeholder="段落標題（例如：刑法口訣）" value="' +
        escHtml(titleStr) + '">' : '') +
      '<div class="aud-editor-hint">每行一句，按儲存後加入朗讀</div>' +
      '<textarea class="aud-editor-textarea" id="aud-editor-text" rows="8" placeholder="輸入你的筆記，每行一句...">' +
        escHtml(pointsText) +
      '</textarea>' +
      '<div class="aud-editor-ai-row">' +
        '<button class="ai-refine-btn" id="aud-ai-refine-btn">✨ AI 整理</button>' +
        '<span class="ai-refine-hint" id="aud-ai-refine-hint"></span>' +
      '</div>' +
      '<div class="aud-editor-btns">' +
        '<button class="btn-primary" id="aud-editor-save">儲存</button>' +
        '<button class="btn-outline" id="aud-editor-cancel">取消</button>' +
        (existing && existing.points && !isCustom
          ? '<button class="btn-warning aud-editor-reset" id="aud-editor-reset">重置為預設</button>' : '') +
        (existing && existing.points && isCustom
          ? '<button class="btn-danger aud-editor-del" id="aud-editor-del">刪除段落</button>' : '') +
      '</div>';

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    function close() { document.body.removeChild(overlay); }

    $q('#aud-editor-cancel', box).addEventListener('click', close);
    overlay.addEventListener('click', function(e){ if (e.target === overlay) close(); });

    // AI 整理按鈕
    $q('#aud-ai-refine-btn', box).addEventListener('click', function(){
      var ta = $q('#aud-editor-text', box);
      aiRefineText(ta, 'audio_note', $q('#aud-ai-refine-hint', box));
    });

    $q('#aud-editor-save', box).addEventListener('click', function() {
      var segTitle = isCustom ? ($q('#aud-editor-seg-title', box).value.trim() || titleStr) : titleStr;
      if (!segTitle) { alert('請輸入段落標題'); return; }
      var rawKey  = noteKey;
      var rawText = $q('#aud-editor-text', box).value;
      var pts = rawText.split('\n').map(function(l){ return l.trim(); }).filter(function(l){ return l.length > 0; });
      USER_AUDIO_NOTES[rawKey] = { title: segTitle, points: pts };
      saveAudioNotesLocal();
      syncAudioNote(rawKey, segTitle, pts);
      close();
      if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); _audUpdateText(); }
    });

    var delBtn = $q('#aud-editor-del', box);
    if (delBtn) {
      delBtn.addEventListener('click', function() {
        if (!confirm('確定刪除這個自訂段落？（可至下方垃圾桶恢復）')) return;
        var note = USER_AUDIO_NOTES[noteKey] || {};
        USER_AUDIO_NOTES[noteKey] = Object.assign({}, note, { _deleted: true });
        saveAudioNotesLocal();
        syncAudioNote(noteKey, '', [], { _deleted: true });
        close();
        if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); _audUpdateText(); }
      });
    }

    var resetBtn = $q('#aud-editor-reset', box);
    if (resetBtn) {
      resetBtn.addEventListener('click', function() {
        if (!confirm('重置為預設內容？你的修改將消失。')) return;
        deleteAudioNote(noteKey);
        close();
        if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); }
      });
    }
  }

  /* ══════════════════════════════════════════════
     重點整理概念卡編輯器
  ══════════════════════════════════════════════ */
  function openConceptNoteEditor(noteKey, subject, topicId, front, back, isCustomCard) {
    var overlay = mk('div', 'aud-editor-overlay');
    var box     = mk('div', 'aud-editor-box');

    var isBlank = (S.dataMode === 'blank');
    var topicSelectHtml = '';

    if (isBlank) {
      // 自主筆記模式：列出使用者已有的自訂主題，以及「＋ 新增主題」選項
      var customPrefix = subject + ':blank_custom_';
      var topicsMap = {};
      Object.keys(USER_CONCEPT_NOTES).forEach(function(k) {
        if (!k.startsWith(customPrefix)) return;
        var note = USER_CONCEPT_NOTES[k];
        if (note._deleted || note._perm_deleted) return;
        if (note.topic_id) topicsMap[note.topic_id] = true;
      });
      var customTopics = Object.keys(topicsMap).sort();

      topicSelectHtml = '<label class="aud-editor-field-label">主題歸類</label>' +
        '<select class="aud-editor-input" id="cne-topic-select">' +
          '<option value="">(未歸類)</option>' +
          customTopics.map(function(t) {
            return '<option value="' + escHtml(t) + '"' + (t === topicId ? ' selected' : '') + '>' + escHtml(t) + '</option>';
          }).join('') +
          '<option value="__new__">(＋ 新增主題)</option>' +
        '</select>' +
        '<input class="aud-editor-input hidden" id="cne-topic-new" placeholder="請輸入新主題名稱" style="margin-top: 6px;">';
    } else {
      // 預設模式：列出預設的系統主題
      var tids = topicsForSubject(subject);
      if (tids.length > 0) {
        topicSelectHtml = '<label class="aud-editor-field-label">主題歸類</label>' +
          '<select class="aud-editor-input" id="cne-topic-select">' +
            '<option value="">(未歸類)</option>' +
            tids.map(function(tid) {
              var t = window.QDB.topics[tid];
              var name = t.short_name || t.name.split('｜').pop();
              return '<option value="' + tid + '"' + (tid === topicId ? ' selected' : '') + '>' + escHtml(name) + '</option>';
            }).join('') +
          '</select>';
      }
    }

    box.innerHTML =
      '<div class="aud-editor-title">' + (isCustomCard ? '✏️ 自訂概念卡' : '✏️ 編輯概念卡') + '</div>' +
      topicSelectHtml +
      '<label class="aud-editor-field-label">標題（卡正面）</label>' +
      '<input class="aud-editor-input" id="cne-front" value="' + escHtml(front) + '" placeholder="概念名稱">' +
      '<label class="aud-editor-field-label">內容（卡背面）</label>' +
      '<div class="aud-editor-hint">支援條列式，每行一個重點</div>' +
      '<textarea class="aud-editor-textarea" id="cne-back" rows="8" placeholder="輸入概念說明…">' +
        escHtml(back) +
      '</textarea>' +
      '<div class="aud-editor-ai-row">' +
        '<button class="ai-refine-btn" id="cne-ai-btn">✨ AI 整理</button>' +
        '<span class="ai-refine-hint" id="cne-ai-hint"></span>' +
      '</div>' +
      '<div class="aud-editor-btns">' +
        '<button class="btn-primary" id="cne-save">儲存</button>' +
        '<button class="btn-outline" id="cne-cancel">取消</button>' +
        '<button class="btn-danger" id="cne-delete">🗑 ' + (isCustomCard ? '刪除' : '刪除此卡') + '</button>' +
        (!isCustomCard && USER_CONCEPT_NOTES[noteKey] && USER_CONCEPT_NOTES[noteKey]._deleted
          ? '<button class="btn-outline" id="cne-restore">↩ 恢復預設</button>' : '') +
      '</div>';

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    function close() { document.body.removeChild(overlay); }

    $q('#cne-cancel', box).addEventListener('click', close);
    overlay.addEventListener('click', function(e){ if (e.target === overlay) close(); });

    $q('#cne-ai-btn', box).addEventListener('click', function(){
      aiRefineText($q('#cne-back', box), 'concept_back', $q('#cne-ai-hint', box));
    });

    var selectEl = $q('#cne-topic-select', box);
    var newTopicInput = $q('#cne-topic-new', box);
    if (selectEl && newTopicInput) {
      selectEl.addEventListener('change', function() {
        if (selectEl.value === '__new__') {
          newTopicInput.classList.remove('hidden');
          newTopicInput.focus();
        } else {
          newTopicInput.classList.add('hidden');
        }
      });
    }

    $q('#cne-save', box).addEventListener('click', function(){
      var newFront = $q('#cne-front', box).value.trim();
      var newBack  = $q('#cne-back',  box).value.trim();
      if (!newFront) { alert('請輸入標題'); return; }

      var savedTopicId = topicId;
      if (selectEl) {
        if (selectEl.value === '__new__') {
          savedTopicId = newTopicInput.value.trim();
          if (!savedTopicId) { alert('請輸入新主題名稱'); return; }
        } else {
          savedTopicId = selectEl.value;
        }
      }

      var data = { subject: subject, topic_id: savedTopicId, front: newFront, back: newBack };
      USER_CONCEPT_NOTES[noteKey] = data;
      saveConceptNotesLocal();
      syncConceptNote(noteKey, data);
      close();
      renderTopicList(); // 保存時同步刷新左側欄主題
      renderConceptArea();
      rebuildAudio(); // 變更卡片分類或內容時，聽讀複習也同步更新
    });

    var delBtn = $q('#cne-delete', box);
    if (delBtn) {
      delBtn.addEventListener('click', function(){
        var msg = isCustomCard ? '確定刪除這張自訂概念卡？（可至下方垃圾桶恢復）' : '確定從畫面刪除這張卡片？（可點「恢復預設」取回）';
        if (!confirm(msg)) return;
        if (isCustomCard) {
          var existing = USER_CONCEPT_NOTES[noteKey] || { front: front, back: back, subject: subject };
          USER_CONCEPT_NOTES[noteKey] = Object.assign({}, existing, { _deleted: true });
          syncConceptNote(noteKey, USER_CONCEPT_NOTES[noteKey]);
        } else {
          USER_CONCEPT_NOTES[noteKey] = { _deleted: true };
          syncConceptNote(noteKey, { _deleted: true });
        }
        saveConceptNotesLocal();
        close();
        renderConceptArea();
        renderTopicList();
        rebuildAudio();
      });
    }
    var restoreBtn = $q('#cne-restore', box);
    if (restoreBtn) {
      restoreBtn.addEventListener('click', function(){
        delete USER_CONCEPT_NOTES[noteKey];
        saveConceptNotesLocal();
        deleteConceptNoteServer(noteKey);
        close();
        renderConceptArea();
      });
    }
  }

  /* ══════════════════════════════════════════════
     聽讀複習
  ══════════════════════════════════════════════ */
  var AUD = {
    synth   : window.speechSynthesis || null,
    voice   : null,
    segs    : [],
    idx     : 0,
    sentIdx : 0,   // 目前段落內第幾句
    playing : false,
    rate    : 0.9,
    inited  : false,
    _session: 0    // 遞增 session ID，防止舊 utterance 的事件影響新播放
  };

  function extractPoints(back) {
    if (!back) return [];
    return back.split('\n').map(function(l) {
      return l.replace(/【[^】]*】/g, '')
               .replace(/^[•✓⚠✗\-\*・📌]\s*/, '')
               .replace(/^\d+[\.、]\s*/, '')
               .replace(/（[^）]{0,20}）/g, '')
               .trim();
    }).filter(function(l) {
      return l.length >= 8 && l.length <= 130 &&
             !/^(共|歷年|複習建議|先理解|再透過|\d+題|必記法條)/.test(l);
    }).slice(0, 12);
  }

  function buildSegments(lsId) {
    AUD.segs = []; AUD.idx = 0; AUD.sentIdx = 0;
    var isBlank = (S.dataMode === 'blank');
    var useDefault = !isBlank;

    if (isBlank) {
      // 自主筆記模式：從用戶自己在此科目下新增的「自訂主題」來建立朗讀段落
      var customPrefix = lsId + ':blank_custom_';
      var topicsMap = {};
      var hasUnclassified = false;
      Object.keys(USER_CONCEPT_NOTES).forEach(function(k) {
        if (!k.startsWith(customPrefix)) return;
        var note = USER_CONCEPT_NOTES[k];
        if (note._deleted || note._perm_deleted) return;
        if (note.topic_id && note.topic_id !== '未分類') topicsMap[note.topic_id] = true;
        else hasUnclassified = true;
      });
      var customTopicNames = Object.keys(topicsMap).sort();
      if (hasUnclassified) {
        customTopicNames.unshift('未分類');
      }

      customTopicNames.forEach(function(tn) {
        // 檢查該自訂主題是否有對應此主題名的自訂段落
        var userNote = USER_AUDIO_NOTES[tn];
        if (userNote && (userNote._deleted || userNote._perm_deleted)) return;
        var hasUserNote = !!(userNote && userNote.points && userNote.points.length);

        var pts = [];
        if (hasUserNote) {
          pts = userNote.points;
        } else {
          // 否則從自主筆記概念卡中抽取重點
          Object.keys(USER_CONCEPT_NOTES).forEach(function(key) {
            if (!key.startsWith(customPrefix)) return;
            var note = USER_CONCEPT_NOTES[key];
            if (note._deleted || note._perm_deleted) return;
            var matches = (tn === '未分類') ? (!note.topic_id || note.topic_id === '未分類') : (note.topic_id === tn);
            if (matches && note.back) {
              var lines = note.back.split('\n').map(function(l) {
                return l.replace(/^[•✓⚠✗\-\*・📌]\s*/, '')
                         .replace(/^\d+[\.、]\s*/, '')
                         .trim();
              }).filter(function(l) { return l.length >= 2; });
              lines.forEach(function(p) {
                if (pts.indexOf(p) < 0 && pts.length < 12) pts.push(p);
              });
            }
          });
        }

        if (!pts.length) return;

        function toSentences(arr) {
          return arr.map(function(p){
            return p.endsWith('。') || p.endsWith('！') || p.endsWith('？') ? p : p + '。';
          });
        }

        var sentences = [tn + '。'].concat(toSentences(pts));
        AUD.segs.push({ title: tn, examCount: 0, sentences: sentences,
                        noteKey: tn, hasUserNote: hasUserNote });
      });
    } else {
      // 預設模式：載入原本的預設主題段落
      topicsForSubject(lsId).forEach(function(tid) {
        var t = window.QDB.topics[tid];
        if (!t) return;
        var name = t.short_name || t.name.split('｜').pop();
        var pts = [], examCount = 0;

        var userNote = USER_AUDIO_NOTES[tid];
        if (userNote && (userNote._deleted || userNote._perm_deleted)) return;   // 已刪除，跳過
        var hasUserNote = !!(userNote && userNote.points && userNote.points.length);

        if (hasUserNote) {
          // 使用者已自訂：直接使用自訂內容（不論模式）
          pts = userNote.points;
        } else if (useDefault) {
          // 預設模式：從 AUDIO_SCRIPTS 或 FLASHCARDS 取得
          var script = window.AUDIO_SCRIPTS && window.AUDIO_SCRIPTS[tid];
          if (script && script.points && script.points.length) {
            pts = script.points.slice();
            examCount = script.exam_count || 0;
          } else {
            var cards = (window.FLASHCARDS || []).concat(window.GENERATED_FLASHCARDS || [])
                          .filter(function(c){ return c.topic === tid; });
            cards.forEach(function(c) {
              // 如果使用者有修改過此系統卡，使用修改後的內容（並採用寬鬆過濾避免短句被濾除）
              var userEdited = USER_CONCEPT_NOTES[c.id];
              if (userEdited && (userEdited._deleted || userEdited._perm_deleted)) return; // 被刪除的卡片不抽出朗讀
              if (userEdited && userEdited.back) {
                var lines = userEdited.back.split('\n').map(function(l) {
                  return l.replace(/^[•✓⚠✗\-\*・📌]\s*/, '')
                           .replace(/^\d+[\.、]\s*/, '')
                           .trim();
                }).filter(function(l) { return l.length >= 2; });
                lines.forEach(function(p) {
                  if (pts.indexOf(p) < 0 && pts.length < 12) pts.push(p);
                });
              } else {
                extractPoints(c.back).forEach(function(p) {
                  if (pts.indexOf(p) < 0 && pts.length < 8) pts.push(p);
                });
              }
            });
          }
        }

        // 加上使用者新增且屬於此主題的自訂概念卡片內容（採用寬鬆過濾，大於等於 2 個字即保留）
        var subjPrefix = lsId + ':custom_';
        Object.keys(USER_CONCEPT_NOTES).forEach(function(key) {
          if (!key.startsWith(subjPrefix)) return;
          var note = USER_CONCEPT_NOTES[key];
          if (note._deleted || note._perm_deleted) return;
          if (note.topic_id === tid && note.back) {
            var lines = note.back.split('\n').map(function(l) {
              return l.replace(/^[•✓⚠✗\-\*・📌]\s*/, '')
                       .replace(/^\d+[\.、]\s*/, '')
                       .trim();
            }).filter(function(l) { return l.length >= 2; });
            lines.forEach(function(p) {
              if (pts.indexOf(p) < 0 && pts.length < 12) pts.push(p);
            });
          }
        });

        // 過濾殘缺句及考題情境句（甲乙丙丁為題目中的當事人，無配合題目無從理解）
        if (!hasUserNote) {
          pts = pts.filter(function(p) {
            var t = p.trim();
            if (!t || t.length < 5) return false;
            if (/[，、]$/.test(t)) return false;        // 殘缺句（以逗號結尾）
            if (/^[甲乙丙丁][^說方、。（【]/.test(t)) return false;  // 情境人物主語
            if (/本題/.test(t)) return false;            // 直接引用題目
            // 中間出現情境人物接動詞：「甲向乙」「丙予以」等
            if (/[，。][甲乙丙丁](?:向|予以|以|出|使|打|殺|傷|燒|毀|奪|騙|竊|詐|拒|持|拿)/.test(t)) return false;
            return true;
          });
        }

        if (!pts.length) return;

        function toSentences(arr) {
          return arr.map(function(p){
            return p.endsWith('。') || p.endsWith('！') || p.endsWith('？') ? p : p + '。';
          });
        }

        var finalPts = hasUserNote ? pts : pts;  // pts 已按邏輯決定
        if (!finalPts.length) return;
        var sentences = [name + '。'].concat(toSentences(finalPts));

        AUD.segs.push({ title: name, examCount: examCount, sentences: sentences,
                        noteKey: tid, hasUserNote: hasUserNote });
      });
    }

    // 加入使用者自訂段落
    // 預設模式：custom|科目|時間戳，以及相容舊格式 custom:
    // 自主筆記模式：blank_custom|科目|時間戳
    Object.keys(USER_AUDIO_NOTES).forEach(function(key) {
      var isBlankFmt = key.startsWith('blank_custom|');
      var isNewFmt   = key.startsWith('custom|');
      var isOldFmt   = key.startsWith('custom:');

      if (isBlank) {
        if (!isBlankFmt) return;
        var parts = key.split('|');
        if (parts[1] !== lsId) return;
      } else {
        if (!isNewFmt && !isOldFmt) return;
        if (isNewFmt) {
          var parts = key.split('|');
          if (parts[1] !== lsId) return;
        }
      }

      var note = USER_AUDIO_NOTES[key];
      if (note._deleted || note._perm_deleted) return;
      if (!note.points || !note.points.length) return;
      var customSents = [note.title + '。'].concat(note.points.map(function(p){
        return p.endsWith('。') || p.endsWith('！') || p.endsWith('？') ? p : p + '。';
      }));
      AUD.segs.push({ title: note.title, examCount: 0, sentences: customSents,
                      noteKey: key, hasUserNote: true, isCustom: true });
    });
  }

  // ── 逐句播放（可同步顯示文字）──────────────────────
  function audPlay() {
    if (!AUD.synth || !AUD.segs.length) return;
    AUD._session++;              // 遞增 session，使舊 utterance 事件失效
    AUD.synth.cancel();
    AUD.playing = true;
    _audUpdateBtn();
    var s = AUD._session;
    // setTimeout 確保 cancel() 的非同步 onerror 事件先行觸發後再開始播放
    setTimeout(function() { if (AUD.playing && AUD._session === s) _audSpeakSentence(); }, 60);
  }

  function _audSpeakSentence() {
    var session = AUD._session;  // 鎖定此次播放的 session
    var seg = AUD.segs[AUD.idx];
    if (!seg) return;
    if (AUD.sentIdx >= seg.sentences.length) {
      if (AUD.idx < AUD.segs.length - 1) {
        AUD.idx++; AUD.sentIdx = 0;
        _audUpdateBtn(); _audScrollList();
        setTimeout(function() {
          if (AUD.playing && AUD._session === session) _audSpeakSentence();
        }, 500);
      } else {
        AUD.playing = false; _audUpdateBtn(); _audUpdateText();
      }
      return;
    }
    _audUpdateText();
    var spokenText = _abbrevLaw(seg.sentences[AUD.sentIdx]);
    var utt = new SpeechSynthesisUtterance(spokenText);
    utt.lang = 'zh-TW'; utt.rate = AUD.rate;
    if (AUD.voice) utt.voice = AUD.voice;
    utt.onend = function() {
      if (AUD.playing && AUD._session === session) { AUD.sentIdx++; _audSpeakSentence(); }
    };
    utt.onerror = function(e) {
      // cancel()/interrupt 為程式主動中斷，忽略即可；真正錯誤才更新按鈕
      if (AUD._session !== session) return;
      if (e && (e.error === 'canceled' || e.error === 'interrupted')) return;
      AUD.playing = false; _audUpdateBtn();
    };
    AUD.synth.speak(utt);
  }

  function audToggle() {
    if (!AUD.synth) return;
    if (AUD.playing) {
      AUD.playing = false;
      AUD.synth.cancel();
      _audUpdateBtn();
    } else {
      audPlay();
    }
  }

  function audStop() {
    if (AUD.synth) AUD.synth.cancel();
    AUD.playing = false; _audUpdateBtn();
  }

  function _audUpdateBtn() {
    var btn = $q('#aud-play-btn');
    if (!btn) return;
    btn.textContent = AUD.playing ? '⏸ 暫停' : '▶ 播放';
    btn.classList.toggle('playing', AUD.playing);
    var ti = $q('#aud-seg-title');
    var pr = $q('#aud-seg-prog');
    if (ti) ti.textContent = AUD.segs[AUD.idx] ? AUD.segs[AUD.idx].title : '';
    if (pr) pr.textContent = AUD.segs.length ? (AUD.idx + 1) + ' / ' + AUD.segs.length + ' 段' : '';
    _audUpdateProgress();
  }

  // 同步顯示目前朗讀的句子（卡拉 OK 效果）
  // 點擊由 initAudioView 中的事件委派處理，不在此綁定
  function _audUpdateText() {
    var display = $q('#aud-text-display');
    if (!display) return;
    var seg = AUD.segs[AUD.idx];
    if (!seg) { display.innerHTML = ''; _audUpdateProgress(); return; }
    display.innerHTML = seg.sentences.map(function(s, i) {
      var cls = 'aud-sent';
      if (i === 0) cls += ' aud-sent-title';
      if (i === AUD.sentIdx) cls += ' aud-sent-active';
      return '<span class="' + cls + '" data-si="' + i + '">' + escHtml(_abbrevLaw(s)) + '</span>';
    }).join('');
    var active = display.querySelector('.aud-sent-active');
    if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    _audUpdateProgress();
  }

  function _audScrollList() {
    var list = $q('#aud-seg-list');
    if (!list) return;
    $a('.aud-seg-item', list).forEach(function(el, i) {
      el.classList.toggle('active', i === AUD.idx);
    });
    var active = list.querySelector('.aud-seg-item.active');
    if (active) active.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  function renderAudSegList() {
    var list = $q('#aud-seg-list');
    if (!list) return;
    if (!AUD.segs.length) {
      list.innerHTML = '<div class="aud-empty">此科目尚無聽讀內容</div>';
    } else {
      list.innerHTML = '';
      AUD.segs.forEach(function(seg, i) {
        var item = mk('div', 'aud-seg-item' + (i === AUD.idx ? ' active' : ''));
        var noteIcon = seg.hasUserNote ? ' <span class="aud-note-dot" title="有自訂筆記">📝</span>' : '';
        item.innerHTML =
          '<span class="aud-seg-num">' + (i + 1) + '</span>' +
          '<span class="aud-seg-label">' + escHtml(seg.title) + noteIcon + '</span>' +
          '<button class="aud-edit-btn" title="編輯筆記">✏️</button>' +
          '<button class="aud-del-btn cc-del-btn" title="刪除此段落">🗑</button>';
        item.querySelector('.aud-seg-label').addEventListener('click', function() {
          audStop(); AUD.idx = i; AUD.sentIdx = 0;
          _audUpdateBtn(); _audScrollList(); _audUpdateText();
        });
        (function(s){
          item.querySelector('.aud-edit-btn').addEventListener('click', function(e) {
            e.stopPropagation();
            openAudioNoteEditor(s.noteKey, s.title, !!s.isCustom);
          });
          item.querySelector('.aud-del-btn').addEventListener('click', function(e) {
            e.stopPropagation();
            if (!confirm('確定刪除此段落？（可至下方垃圾桶恢復）')) return;
            // 保留原內容，僅加上刪除標記，方便恢復
            var existing = USER_AUDIO_NOTES[s.noteKey] || {};
            USER_AUDIO_NOTES[s.noteKey] = Object.assign({}, existing, { _deleted: true });
            saveAudioNotesLocal();
            syncAudioNote(s.noteKey, existing.title || s.title, existing.points || []);
            if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); }
          });
        })(seg);
        list.appendChild(item);
      });
      _audUpdateText();
    }

    // 「新增自訂段落」按鈕（自訂段落與模式綁定，確保互不干擾）
    var addBtn = mk('button', 'aud-add-custom-btn', '＋ 新增自訂段落');
    addBtn.addEventListener('click', function() {
      var isBlank = (S.dataMode === 'blank');
      var subj = S.lawSubject || 'general';
      var prefix = isBlank ? 'blank_custom|' : 'custom|';
      openAudioNoteEditor(prefix + subj + '|' + Date.now(), '', true);
    });
    list.appendChild(addBtn);

    // ── 聽讀垃圾桶 ───────────────────────────────
    renderAudioTrash(list);
  }

  function _audSegTitle(key) {
    // 取得段落顯示標題：自訂段落用儲存的 title，系統主題用 topic 名稱
    var n = USER_AUDIO_NOTES[key];
    if (n && n.title) return n.title;
    var t = window.QDB.topics[key];
    if (t) return t.short_name || t.name.split('｜').pop();
    // 新格式：custom|或 blank_custom|
    if (key.startsWith('custom|') || key.startsWith('blank_custom|')) {
      return key.split('|').slice(2).join('|') || '自訂段落';
    }
    return key.replace(/^custom:/, '');
  }

  function renderAudioTrash(list) {
    // 蒐集屬於目前科目、被 _deleted 的段落
    var isBlank = (S.dataMode === 'blank');
    var subjTids = topicsForSubject(S.lawSubject);
    var deletedKeys = Object.keys(USER_AUDIO_NOTES).filter(function(key){
      var n = USER_AUDIO_NOTES[key];
      if (!n._deleted) return false;
      if (isBlank) {
        if (key.startsWith('blank_custom|')) {
          return key.split('|')[1] === S.lawSubject;
        }
        var customPrefix = S.lawSubject + ':blank_custom_';
        if (key === '未分類') {
          return Object.keys(USER_CONCEPT_NOTES).some(function(ck){
            if (!ck.startsWith(customPrefix)) return false;
            var cn = USER_CONCEPT_NOTES[ck];
            return cn && !cn._deleted && !cn._perm_deleted && (!cn.topic_id || cn.topic_id === '未分類');
          });
        } else {
          return Object.keys(USER_CONCEPT_NOTES).some(function(ck){
            if (!ck.startsWith(customPrefix)) return false;
            var cn = USER_CONCEPT_NOTES[ck];
            return cn && !cn._deleted && !cn._perm_deleted && cn.topic_id === key;
          });
        }
      } else {
        if (key.startsWith('custom|')) {
          return key.split('|')[1] === S.lawSubject;
        }
        return key.startsWith('custom:') || subjTids.indexOf(key) > -1;
      }
    });
    if (!deletedKeys.length) return;

    var sec = mk('div', 'trash-section');
    var hdr = mk('div', 'trash-header');
    hdr.innerHTML =
      '<span class="trash-header-title">🗑 垃圾桶（' + deletedKeys.length + ' 段）</span>' +
      '<span class="trash-header-toggle">▼</span>';
    var body = mk('div', 'trash-body hidden');
    sec.appendChild(hdr); sec.appendChild(body);
    hdr.addEventListener('click', function(){
      body.classList.toggle('hidden');
      hdr.querySelector('.trash-header-toggle').textContent = body.classList.contains('hidden') ? '▼' : '▲';
    });

    deletedKeys.forEach(function(key){
      var isCustom = key.startsWith('custom:') || key.startsWith('custom|') || key.startsWith('blank_custom|');
      var label = _audSegTitle(key);
      var item = mk('div', 'trash-item');
      item.appendChild(mk('span', 'trash-item-label', '🎧 ' + escHtml(label)));
      var restoreBtn = mk('button', 'trash-restore-btn', '↩ 恢復');
      var permBtn    = mk('button', 'trash-perm-del-btn', '🗑 永久刪除');
      item.appendChild(restoreBtn); item.appendChild(permBtn);
      body.appendChild(item);

      restoreBtn.addEventListener('click', function(){
        var n = USER_AUDIO_NOTES[key];
        if (isCustom && (!n || !n.points || !n.points.length)) {
          // 自訂段落已無內容，無法恢復
          delete USER_AUDIO_NOTES[key];
          alert('此自訂段落已無內容，無法恢復');
        } else if (n) {
          delete n._deleted;
          syncAudioNote(key, n.title || '', n.points || []);
        }
        saveAudioNotesLocal();
        if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); }
      });
      permBtn.addEventListener('click', function(){
        if (!confirm('確定永久刪除「' + label + '」？此操作無法恢復。')) return;
        if (isCustom) {
          delete USER_AUDIO_NOTES[key];
          deleteAudioNote(key);
        } else {
          USER_AUDIO_NOTES[key] = { _perm_deleted: true };
          syncAudioNote(key, '', [], { _perm_deleted: true });
        }
        saveAudioNotesLocal();
        if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); }
      });
    });
    list.appendChild(sec);
  }

  // ── 法律名稱縮寫（用於朗讀文字顯示及 TTS 輸出）──────────────
  function _abbrevLaw(text) {
    var map = [
      ['刑事訴訟法', '刑訴法'], ['民事訴訟法', '民訴法'],
      ['行政程序法', '行程法'], ['行政訴訟法', '行訴法'],
      ['行政罰法',   '行罰法'], ['證券交易法', '證交法'],
      ['強制執行法', '強執法'], ['國家賠償法', '國賠法'],
      ['地方制度法', '地制法'], ['公務員服務法', '公服法'],
      ['公務員懲戒法', '公懲法'], ['勞動基準法', '勞基法']
    ];
    map.forEach(function(p) { text = text.split(p[0]).join(p[1]); });
    // 法律名稱後的「第X條」→「X條」（刑訴法第33條 → 刑訴法33條）
    text = text.replace(/(刑訴法|民訴法|行程法|行訴法|行罰法|證交法|強執法|國賠法|地制法|公服法|公懲法|勞基法|刑法|民法|保險法|公司法|票據法|海商法|憲法)第(\d)/g, '$1$2');
    // XX條第N項 → XX條N項
    text = text.replace(/(\d+條(?:之\d+)?)第(\d+)項/g, '$1$2項');
    return text;
  }

  // ── 進度條輔助 ────────────────────────────────────────────────
  function _audTotalSents() {
    return AUD.segs.reduce(function(sum, seg) { return sum + seg.sentences.length; }, 0);
  }
  function _audCurPos() {
    var pos = 0;
    for (var i = 0; i < AUD.idx; i++) pos += AUD.segs[i].sentences.length;
    return pos + AUD.sentIdx;
  }
  function _audUpdateProgress() {
    var bar = $q('#aud-progress');
    if (!bar) return;
    var total = _audTotalSents();
    bar.max = Math.max(total - 1, 0);
    bar.value = _audCurPos();
  }
  function _audSeekToPos(pos) {
    var cum = 0;
    for (var i = 0; i < AUD.segs.length; i++) {
      var len = AUD.segs[i].sentences.length;
      if (cum + len > pos) { AUD.idx = i; AUD.sentIdx = pos - cum; return; }
      cum += len;
    }
    if (AUD.segs.length > 0) {
      AUD.idx = AUD.segs.length - 1;
      AUD.sentIdx = Math.max(0, AUD.segs[AUD.idx].sentences.length - 1);
    }
  }

  function initAudioView() {
    var area = $q('#audio-player-area');
    if (!area) return;
    if (AUD.synth) {
      var setVoice = function() {
        var v = AUD.synth.getVoices().find(function(v){ return /zh/i.test(v.lang); });
        if (v) AUD.voice = v;
      };
      setVoice();
      AUD.synth.onvoiceschanged = setVoice;
    }

    var isBlank = (S.dataMode === 'blank');
    area.innerHTML =
      '<div class="aud-player">' +
        (!AUD.synth ? '<div class="aud-unsupported">⚠️ 此瀏覽器不支援語音朗讀<br>請改用 <b>Chrome</b> 瀏覽器開啟本網站即可使用</div>' : '') +
        '<div class="aud-data-mode-row">' +
          '<span class="dm-label">📂 資料模式：</span>' +
          '<button class="dm-btn' + (!isBlank ? ' dm-btn-active' : '') + '" id="aud-dm-default">📚 預設資料</button>' +
          '<button class="dm-btn' + (isBlank  ? ' dm-btn-active' : '') + '" id="aud-dm-blank">✏️ 自主筆記</button>' +
        '</div>' +
        '<div class="aud-header">' +
          '<button class="aud-nav-btn" id="aud-prev">⏮</button>' +
          '<div class="aud-seg-info">' +
            '<div class="aud-seg-title" id="aud-seg-title">請選擇上方科目</div>' +
            '<div class="aud-seg-prog"  id="aud-seg-prog"></div>' +
          '</div>' +
          '<button class="aud-nav-btn" id="aud-next">⏭</button>' +
        '</div>' +
        '<div class="aud-text-display" id="aud-text-display"></div>' +
        '<div class="aud-controls">' +
          '<div class="aud-rate-row">' +
            '<span class="aud-rate-label">速度</span>' +
            '<input type="range" id="aud-rate" class="aud-rate-slider" min="0.5" max="2.5" step="0.25" value="' + AUD.rate + '">' +
            '<span class="aud-rate-val" id="aud-rate-val">' + AUD.rate.toFixed(2) + 'x</span>' +
          '</div>' +
          '<button class="aud-play-btn" id="aud-play-btn">▶ 播放</button>' +
        '</div>' +
        '<div class="aud-note">點選句子可跳至該處播放・點列表標題可跳段・播完自動接下一段</div>' +
        '<div class="aud-seg-list" id="aud-seg-list"><div class="aud-empty">請選擇上方科目</div></div>' +
      '</div>';

    // ── 資料模式切換 ─────────────────────────────
    $q('#aud-dm-default').addEventListener('click', function() {
      if (S.dataMode === 'default') return;
      S.dataMode = 'default'; S.topic = null; saveLocalDataMode();
      // 重建 UI（含模式按鈕高亮）
      AUD.inited = false;
      initAudioView();
      renderTopicList(); // 切換時同步更新左側欄主題
      rebuildAudio();
      renderConceptArea();
    });
    $q('#aud-dm-blank').addEventListener('click', function() {
      if (S.dataMode === 'blank') return;
      S.dataMode = 'blank'; S.topic = null; saveLocalDataMode();
      AUD.inited = false;
      initAudioView();
      renderTopicList(); // 切換時同步更新左側欄主題
      rebuildAudio();
      renderConceptArea();
    });

    // ── 上/下段 ──────────────────────────────────
    $q('#aud-prev').addEventListener('click', function() {
      audStop(); AUD.idx = Math.max(0, AUD.idx - 1); AUD.sentIdx = 0;
      _audUpdateBtn(); _audScrollList(); _audUpdateText();
    });
    $q('#aud-next').addEventListener('click', function() {
      audStop(); AUD.idx = Math.min(AUD.segs.length - 1, AUD.idx + 1); AUD.sentIdx = 0;
      _audUpdateBtn(); _audScrollList(); _audUpdateText();
    });
    $q('#aud-play-btn').addEventListener('click', audToggle);
    $q('#aud-rate').addEventListener('input', function() {
      AUD.rate = parseFloat(this.value);
      $q('#aud-rate-val').textContent = AUD.rate.toFixed(2) + 'x';
      if (AUD.playing) {
        AUD._session++;
        AUD.synth.cancel();
        var s = AUD._session;
        setTimeout(function() { if (AUD.playing && AUD._session === s) _audSpeakSentence(); }, 60);
      }
    });

    // ── 事件委派：點選句子跳播（不論 innerHTML 如何重建都有效）──
    var display = $q('#aud-text-display');
    display.addEventListener('click', function(e) {
      var span = e.target.closest('.aud-sent');
      if (!span || span.classList.contains('aud-sent-title')) return;
      var i = parseInt(span.dataset.si, 10);
      if (isNaN(i)) return;
      AUD.sentIdx = i;
      _audUpdateText();          // 更新高亮顯示
      AUD._session++;            // 遞增 session，使任何舊 utterance 事件失效
      if (AUD.synth) AUD.synth.cancel();
      var s = AUD._session;
      AUD.playing = true;
      _audUpdateBtn();
      setTimeout(function() {
        if (AUD.playing && AUD._session === s) _audSpeakSentence();
      }, 60);
    });

    AUD.inited = true;
  }

  /* ══════════════════════════════════════════════
     手機 Tab Bar
  ══════════════════════════════════════════════ */
  function initMobileTabBar() {
    $a('.mbar-btn').forEach(function(btn){
      btn.addEventListener('click', function(){ setMobileView(btn.dataset.mview); });
    });
  }

  function initMobileLawBar() {
    var bar = $q('#mobile-law-tabs');
    if (!bar) return;
    var subs = window.QDB.law_subjects.filter(function(ls){
      return !EXCLUDED_SUBJECTS.includes(ls.id);
    });
    subs.forEach(function(ls){
      var btn = mk('button', 'm-ltab', escHtml(ls.id));
      btn.dataset.ls = ls.id;
      btn.addEventListener('click', function(){ selectLawSubject(ls.id); });
      bar.appendChild(btn);
    });
    CUSTOM_SUBJECTS.forEach(function(cs){
      bar.appendChild(makeCustomMobileTab(cs));
    });
    var addBtn = mk('button', 'm-ltab m-ltab-add', '＋');
    addBtn.title = '新增自訂科目';
    addBtn.addEventListener('click', promptAddCustomSubject);
    bar.appendChild(addBtn);
  }

  function setMobileView(view) {
    if (!isMobile()) return;
    if (S.mview === 'audio' && view !== 'audio') { audStop(); hide('panel-audio'); }
    S.mview = view;
    updateMbarActive();
    $a('.mobile-view').forEach(function(v){ v.classList.add('hidden'); });
    if (view === 'audio') {
      // 手機聽讀與桌機共用 panel-audio，不用 overlay
      hide('panel-concept'); hide('panel-quiz'); show('panel-audio');
      $a('.mtab').forEach(function(b){ b.classList.toggle('active', b.dataset.mode === 'audio'); });
      S.mode = 'audio';
      renderTopicList(); // 手機切換模式同步更新主題列表
      if (!AUD.inited) {
        initAudioView();
      } else {
        var aDef = $q('#aud-dm-default');
        var aBlk = $q('#aud-dm-blank');
        if (aDef) aDef.classList.toggle('dm-btn-active', S.dataMode === 'default');
        if (aBlk) aBlk.classList.toggle('dm-btn-active', S.dataMode === 'blank');
      }
      rebuildAudio();
      return;
    }
    if (view === 'account') {
      show('mview-account'); renderMobileAuth();
    } else if (view === 'concept') {
      hide('panel-quiz'); show('panel-concept');
      hide('quiz-nav'); $q('#main').classList.remove('quiz-active');
      $a('.mtab').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='concept'); });
      S.mode = 'concept';
      renderTopicList(); // 手機切換模式同步更新主題列表
      renderConceptArea();
      requestAnimationFrame(function(){ document.documentElement.scrollTop = 0; document.body.scrollTop = 0; });
    } else if (view === 'quiz') {
      hide('panel-concept'); show('panel-quiz');
      $a('.mtab').forEach(function(b){ b.classList.toggle('active', b.dataset.mode==='quiz'); });
      S.mode = 'quiz';
      renderTopicList(); // 手機切換模式同步更新主題列表
      updateTopicChip();
      renderTopicChipsBar();
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
    var startX = 0, startY = 0;
    main.addEventListener('touchstart', function(e){
      startX = e.changedTouches[0].clientX;
      startY = e.changedTouches[0].clientY;
    }, { passive:true });
    main.addEventListener('touchend', function(e){
      if (S.mode !== 'quiz' || !S.pool.length) return;
      var dx = e.changedTouches[0].clientX - startX;
      var dy = e.changedTouches[0].clientY - startY;
      // 僅在水平位移明顯大於垂直時才換題（避免垂直滾動誤觸）
      if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) goQuestion(dx < 0 ? 1 : -1);
    }, { passive:true });
  }

  /* ══════════════════════════════════════════════
     Sidebar 收合
  ══════════════════════════════════════════════ */
  function initSidebar() {
    var tab = $q('#sidebar-tab');
    $q('#collapse-btn').addEventListener('click', function(){
      S.sidebarOpen = !S.sidebarOpen;
      $q('#sidebar').classList.toggle('collapsed', !S.sidebarOpen);
      $q('#collapse-btn').textContent = S.sidebarOpen ? '◀' : '▶';
      if (tab) tab.classList.toggle('hidden', S.sidebarOpen);
    });
    if (tab) {
      tab.addEventListener('click', function(){
        S.sidebarOpen = true;
        $q('#sidebar').classList.remove('collapsed');
        $q('#collapse-btn').textContent = '◀';
        tab.classList.add('hidden');
      });
    }
  }

  /* ══════════════════════════════════════════════
     動態載入（延遲大型資料檔，加快首屏開啟速度）
  ══════════════════════════════════════════════ */
  var _scriptState   = {};   // url -> 'loading' | 'ready'
  var _scriptWaiters = {};   // url -> [callback,...]

  function loadScriptOnce(url, cb) {
    if (_scriptState[url] === 'ready') { if (cb) cb(); return; }
    if (cb) (_scriptWaiters[url] = _scriptWaiters[url] || []).push(cb);
    if (_scriptState[url] === 'loading') return;
    _scriptState[url] = 'loading';
    var s = document.createElement('script');
    s.src = url;
    s.onload = function () {
      _scriptState[url] = 'ready';
      (_scriptWaiters[url] || []).forEach(function (f) { f(); });
      _scriptWaiters[url] = [];
    };
    s.onerror = function () {
      _scriptState[url] = undefined;   // 允許之後重試
      (_scriptWaiters[url] || []).forEach(function (f) { f(); });
      _scriptWaiters[url] = [];
    };
    document.head.appendChild(s);
  }

  function explReady() { return _scriptState['js/explanations_data.js'] === 'ready'; }
  function ensureExpl(cb)  { loadScriptOnce('js/explanations_data.js', cb); }
  function ensureAudio(cb) { loadScriptOnce('js/audio_scripts.js', cb); }

  function rebuildAudio() {
    ensureAudio(function () {
      if (S.lawSubject) { buildSegments(S.lawSubject); renderAudSegList(); _audUpdateBtn(); _audUpdateText(); }
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
    loadLocalCustomSubjects();
    loadLocalConceptNotes();
    loadLocalDataMode();
    loadAudioNotes();
    initAuthPanel();
    updateAuthUI();
    initLawTabs();
    initModeTabs();
    initFilterBar();
    initMobileTabBar();
    initMobileLawBar();
    initSwipe();
    initSidebar();
    if (S.token) {
      loadServerProgress();
      loadServerAudioNotes();
      loadServerBookmarks();
      loadServerQnotes();
      loadServerConceptNotes();
      loadServerCustomSubjects();
    }
    updateStatBadge();
    if (isMobile()) setMobileView('quiz');
    // 首屏渲染完後，於背景預載詳解資料（最大檔，答題看詳解時才需要）
    setTimeout(function () { ensureExpl(); }, 300);
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
