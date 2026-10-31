/* ============================================================
   砚 Inkstone — 前端逻辑
   ============================================================ */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const SKILL_DESC = {
  'book-analysis': '扫榜、六维拆文、提取可对齐的文风',
  'novel-engine': '立项到大纲到章节，文档驱动，长篇不跑偏',
  'chapter-craft': '场景四问、爽点冷却、章末钩子',
  'scene-craft': '对话潜台词、战斗节奏、情感克制',
  'character-world': '角色卡、关系图谱、世界规则与考据',
  'interactive': '抉择式推进，像跑团一样写故事',
  'short-drama': '分集钩子、四层反派、节奏曲线',
  'deai': '32 类 AI 模式（含 6 条中文病句），分级判定',
  'review': '编辑 / 读者 / 平台 / 作者四维挑错',
  'seven-step': '宪法 → 规格 → 澄清 → 计划 → 任务 → 写作 → 验证',
  'wechat-article': '标题公式、三种结构、禁忌词与四层自检',
  'official-doc': '文种体例、事实纪律、复核清单',
  'brand-voice': '人称、句长、禁词，写成一张卡',
  'research-deep': '纵向追时间，横向比竞品，交汇出判断',
  'work-comms': '3P 周报、向上汇报、事故复盘',
  'academic-polish': '保真优先，断言强度不许上移',
  'longform': '大纲协作、逐节反馈、引用规范',
  'doc-coauthor': '三阶段共创 + 读者盲测',
  'academic': '框架、逐段起草、四遍审稿',
};

const PROJECT_FIELDS = [
  ['title', '作品名', 'input', '例如：长夜将尽'],
  ['genre', '类型 / 题材', 'input', '玄幻 / 悬疑 / 都市 / 历史…'],
  ['audience', '目标读者', 'input', '男频爽文 / 女性向 / 泛大众…'],
  ['logline', '一句话故事', 'textarea', '谁，想要什么，被什么挡住'],
  ['characters', '人物设定', 'textarea', '每个角色：欲望 / 恐惧 / 秘密 / 底线 / 说话方式'],
  ['world', '世界观与规则', 'textarea', '硬规则与代价、势力、地理、时代考据'],
  ['outline', '大纲', 'textarea', '分卷、章节路线、关键转折'],
  ['style', '文风要求', 'textarea', '参考作家、句长、叙述视角、禁忌'],
  ['notes', '其他备注', 'textarea', '任何希望模型一直记住的东西'],
];

const S = {
  skills: [],
  config: null,
  convs: [],
  bgs: [],
  current: null,
  skillId: 'novel-engine',
  view: 'write',
  streaming: false,
  ctrl: null,
  live: null,
  project: {},
  projectTimer: null,
  workflow: null,
  wfStep: 0,
};

let draftCfg = null;
let editPid = null;
let curTab = 'model';
let savedCfg = null;
let settingsSaved = false;

/* ---------------------------------------------------------- 工具 */
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
  .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function toast(msg, ms = 2200) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove('show'), ms);
}

async function api(method, url, body) {
  const opt = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const r = await fetch(url, opt);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || ('请求失败 ' + r.status));
  return d;
}

function scrollBottom(smooth) {
  const sc = $('#scroll');
  sc.scrollTo({ top: sc.scrollHeight, behavior: smooth ? 'smooth' : 'auto' });
}
function nearBottom() {
  const sc = $('#scroll');
  return sc.scrollHeight - sc.scrollTop - sc.clientHeight < 160;
}

/* ---------------------------------------------------------- Markdown */
function inline(t) {
  const codes = [];
  t = t.replace(/`([^`\n]+)`/g, (m, c) => {
    codes.push(c);
    return '\u0000' + (codes.length - 1) + '\u0000';
  });
  t = t.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  t = t.replace(/~~([^~\n]+)~~/g, '<del>$1</del>');
  t = t.replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/\u0000(\d+)\u0000/g, (m, i) => '<code>' + codes[+i] + '</code>');
  return t;
}

const indentOf = s => (s.match(/^\s*/) || [''])[0].length;
const splitRow = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(s => s.trim());

/* 由技能主色推导出深色与浅色，避免按钮 hover 变成另一种颜色 */
function hex2rgb(h) {
  h = String(h).replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function shade(hex, p) {
  const [r, g, b] = hex2rgb(hex);
  const f = x => Math.max(0, Math.min(255, Math.round(x * (1 + p))));
  return '#' + [f(r), f(g), f(b)].map(x => x.toString(16).padStart(2, '0')).join('');
}
function mix(hex, to, p) {
  const a = hex2rgb(hex), b = hex2rgb(to);
  const f = (x, i) => Math.round(x * (1 - p) + b[i] * p);
  return '#' + [0, 1, 2].map(i => f(a[i], i).toString(16).padStart(2, '0')).join('');
}

function parseList(lines, i) {
  const ordered = /^\s*\d+\./.test(lines[i]);
  const tag = ordered ? 'ol' : 'ul';
  const baseIndent = indentOf(lines[i]);
  let html = '<' + tag + '>';
  while (i < lines.length) {
    const m = lines[i].match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/);
    if (!m) break;
    const ind = m[1].length;
    if (ind < baseIndent) break;
    if (ind > baseIndent) {
      const sub = parseList(lines, i);
      if (sub.next === i) break;
      html = html.replace(/<\/li>$/, sub.html + '</li>');
      i = sub.next;
      continue;
    }
    html += '<li>' + inline(esc(m[3])) + '</li>';
    i++;
  }
  html += '</' + tag + '>';
  return { html, next: i };
}

function md(src) {
  // 模型输出可能带 \r\n 甚至 \r\r\n，先统一换行，否则行尾 \r 会让下面的正则失配
  const lines = String(src || '').replace(/\r\n?/g, '\n').split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (/^```/.test(line)) {
      const lang = line.slice(3).trim();
      i++;
      const buf = [];
      while (i < lines.length && !/^```/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++;
      out.push('<pre><code>' + esc(buf.join('\n')) + '</code></pre>');
      continue;
    }
    if (!line.trim()) { i++; continue; }

    if (/^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$/.test(line.trim())) {
      out.push('<hr>'); i++; continue;
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      const lv = h[1].length;
      out.push('<h' + lv + '>' + inline(esc(h[2])) + '</h' + lv + '>');
      i++; continue;
    }
    if (line.trim().startsWith('|') && lines[i + 1] &&
      /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      const head = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) { rows.push(splitRow(lines[i])); i++; }
      let t = '<table><thead><tr>' + head.map(c => '<th>' + inline(esc(c)) + '</th>').join('') + '</tr></thead><tbody>';
      rows.forEach(r => { t += '<tr>' + r.map(c => '<td>' + inline(esc(c)) + '</td>').join('') + '</tr>'; });
      out.push(t + '</tbody></table>');
      continue;
    }
    if (/^>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, '')); i++; }
      out.push('<blockquote>' + md(buf.join('\n')) + '</blockquote>');
      continue;
    }
    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const r = parseList(lines, i);
      if (r.next > i) { out.push(r.html); i = r.next; continue; }
      // 解析器没能推进（异常行），交给下面的兜底分支处理
    }
    const buf = [];
    while (i < lines.length && lines[i].trim() &&
      !/^```/.test(lines[i]) && !/^#{1,6}\s/.test(lines[i]) &&
      !/^>\s?/.test(lines[i]) && !/^\s*([-*+]|\d+\.)\s+/.test(lines[i]) &&
      !lines[i].trim().startsWith('|')) {
      buf.push(lines[i]); i++;
    }
    if (!buf.length) {
      // 兜底：任何未被上面分支吃掉的单行（例如流式过程中还没写完的表格行）
      // 必须原样输出并推进游标，否则会死循环。
      out.push('<p>' + inline(esc(line)) + '</p>');
      i++;
      continue;
    }
    out.push('<p>' + inline(esc(buf.join('\n'))).replace(/\n/g, '<br>') + '</p>');
  }
  return out.join('\n');
}

/* ---------------------------------------------------------- 启动 */
async function boot() {
  try {
    const d = await api('GET', '/api/bootstrap');
    S.skills = d.skills || [];
    S.config = d.config;
    S.convs = d.conversations || [];
    S.bgs = d.backgrounds || [];
    await loadBooks();
    if (!S.skills.find(s => s.id === S.skillId) && S.skills[0]) S.skillId = S.skills[0].id;
    if (!S.convs.length && !BK.list.length) S.view = 'skills';
    const qs = new URLSearchParams(location.search);
    if (qs.get('view')) S.view = qs.get('view');
    else {
      try {
        const sv = localStorage.getItem('inkstone.view');
        if (sv && ['write', 'book', 'skills', 'project', 'corpus'].includes(sv)) S.view = sv;
      } catch (_) { }
    }
    if (qs.get('tab')) BK.tab = qs.get('tab');
    if (qs.get('q')) BK.pendingQuery = qs.get('q');
    applyAppearance();
    renderSkill();
    setView(S.view);
    renderThread();
    renderInspector();
    updateModelChip();
    bindEvents();
    const prov = (S.config.providers || []).find(p => p.id === S.config.activeProviderId);
    const ready = prov && (prov.apiKey || prov.kind === 'ollama' ||
      /localhost|127\.0\.0\.1/.test(prov.baseUrl || ''));
    if (!ready) setTimeout(() => toast('先在左下角选一个模型，就能开始写了', 4200), 800);
  } catch (e) {
    document.body.innerHTML = '<div style="padding:60px;font-family:serif">' +
      '<h2>无法连接本地服务</h2><p style="color:#777">' + esc(e.message) + '</p>' +
      '<p style="color:#777">请确认 server.py 正在运行。</p></div>';
  }
}

/* ---------------------------------------------------------- 技能 */
function currentSkill() {
  return S.skills.find(s => s.id === S.skillId) || S.skills[0];
}

function renderSkill() {
  const wf = currentWorkflow();
  if (wf) {
    const n = wf.steps.length;
    const i = Math.min(Math.max(S.wfStep, 0), n - 1);
    $('#skillName').textContent = wf.name + ' · ' + (i + 1) + '/' + n;
    $('#skillAccent').style.background = wf.accent || '#B23A2F';
    renderStages();
    return;
  }
  const sk = currentSkill();
  if (!sk) return;
  $('#skillName').textContent = sk.name;
  $('#skillAccent').style.background = sk.accent || '#B23A2F';
  renderStages();
}

function wfName(id) {
  if (typeof WORKFLOWS === 'undefined') return '';
  const w = WORKFLOWS.find(x => x.id === id);
  return w ? w.name : '';
}

function currentWorkflow() {
  if (!S.workflow) return null;
  if (typeof WORKFLOWS === 'undefined') return null;
  return WORKFLOWS.find(x => x.id === S.workflow) || null;
}

let wfSaveTimer = null;
function saveWorkflow() {
  clearTimeout(wfSaveTimer);
  wfSaveTimer = setTimeout(async () => {
    if (!S.current || !S.current.id) return;
    try {
      await api('PATCH', '/api/conversations/' + S.current.id,
        { workflowId: S.workflow || '', workflowStep: S.wfStep });
    } catch (_) { }
  }, 400);
}

async function startWorkflow(id) {
  const wf = (typeof WORKFLOWS === 'undefined') ? null : WORKFLOWS.find(x => x.id === id);
  if (!wf) return;
  const hasMsgs = S.current && (S.current.messages || []).length;
  if (hasMsgs) {
    if (!confirm('当前会话里已经有内容。\n\n开一个新会话跑「' + wf.name + '」？')) return;
    await newConv();
  }
  S.workflow = id;
  S.wfStep = 0;
  S.skillId = wf.steps[0].skill;
  if (S.view !== 'write') setView('write');
  renderSkill();
  renderPanel();
  renderInspector();
  goWorkflowStep(0);
  toast('已进入「' + wf.name + '」，按底部步骤往下走', 3000);
}

function exitWorkflow() {
  S.workflow = null;
  S.wfStep = 0;
  renderSkill();
  renderPanel();
  renderInspector();
  saveWorkflow();
  toast('已退出工作流');
}

function goWorkflowStep(i) {
  const wf = currentWorkflow();
  if (!wf) return;
  const st = wf.steps[i];
  if (!st) return;
  S.wfStep = i;
  S.skillId = st.skill;
  renderSkill();
  renderPanel();
  renderInspector();
  const ta = $('#input');
  ta.value = st.prompt || '';
  ta.focus();
  autosize();
  ta.setSelectionRange(ta.value.length, ta.value.length);
  saveWorkflow();
}

function renderStages() {
  const box = $('#stages');
  box.innerHTML = '';
  const wf = currentWorkflow();
  box.classList.toggle('wf-mode', !!wf);
  if (wf) {
    wf.steps.forEach((st, i) => {
      const b = document.createElement('button');
      b.className = 'stage wf' + (i === S.wfStep ? ' on' : '') + (i < S.wfStep ? ' done' : '');
      b.title = st.hint || '';
      b.innerHTML = '<i class="wf-n">' + (i < S.wfStep ? '✓' : (i + 1)) + '</i>' + esc(st.name);
      b.onclick = () => goWorkflowStep(i);
      box.appendChild(b);
    });
    const x = document.createElement('button');
    x.className = 'stage wf-exit';
    x.textContent = '退出';
    x.title = '回到单个技能';
    x.onclick = exitWorkflow;
    box.appendChild(x);
    return;
  }
  const sk = currentSkill();
  (sk.stages || []).forEach((st, idx) => {
    const b = document.createElement('button');
    b.className = 'stage';
    b.textContent = st.name;
    b.title = st.hint || '';
    b.onclick = () => {
      const ta = $('#input');
      ta.value = st.hint || '';
      ta.focus();
      autosize();
      ta.setSelectionRange(ta.value.length, ta.value.length);
    };
    box.appendChild(b);
  });
}

function openSkillPop() {
  const body = $('#skillPopBody');
  const groups = {};
  S.skills.forEach(s => { (groups[s.category] = groups[s.category] || []).push(s); });
  let html = '';
  Object.keys(groups).forEach(g => {
    html += '<div class="pop-group">' + esc(g) + '</div>';
    groups[g].forEach(s => {
      html += '<button class="pop-item' + (s.id === S.skillId ? ' active' : '') + '" data-skill="' + s.id + '">' +
        '<span class="pdot" style="background:' + s.accent + '"></span>' +
        '<span class="ptext"><span class="pname">' + esc(s.name) + '</span>' +
        '<span class="pdesc">' + esc(SKILL_DESC[s.id] || s.tag || '') + '</span></span></button>';
    });
  });
  let wfHtml = '';
  if (typeof WORKFLOWS !== 'undefined' && WORKFLOWS.length) {
    wfHtml = '<div class="pop-group">工作流</div>';
    WORKFLOWS.forEach(w => {
      wfHtml += '<button class="pop-item' + (S.workflow === w.id ? ' active' : '') +
        '" data-wf="' + w.id + '">' +
        '<span class="pdot" style="background:' + (w.accent || '#B23A2F') + '"></span>' +
        '<span class="ptext"><span class="pname">' + esc(w.name) + '</span>' +
        '<span class="pdesc">' + esc(w.desc) + '</span></span></button>';
    });
    if (S.workflow) {
      wfHtml += '<button class="pop-item" data-wf="">' +
        '<span class="pdot" style="background:var(--muted-2)"></span>' +
        '<span class="ptext"><span class="pname">退出工作流</span>' +
        '<span class="pdesc">回到单个技能</span></span></button>';
    }
  }
  body.innerHTML = wfHtml + html;
  const pop = $('#skillPop');
  pop.classList.add('show');
  $('#skillMask').classList.add('show');
}

function closeSkillPop() {
  $('#skillPop').classList.remove('show');
  $('#skillMask').classList.remove('show');
}

async function pickSkill(id) {
  S.skillId = id;
  closeSkillPop();
  renderSkill();
  if (S.current) {
    S.current.skillId = id;
    try { await api('PATCH', '/api/conversations/' + S.current.id, { skillId: id }); } catch (e) { }
  }
  if (!S.current || !(S.current.messages || []).length) renderThread();
  renderPanel();
  renderInspector();
}

/* ---------------------------------------------------------- 会话列表 */
function fmtTime(ts) {
  const d = new Date(ts * 1000);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.getHours().toString().padStart(2, '0') + ':' + d.getMinutes().toString().padStart(2, '0');
  const y = new Date(now.getTime() - 86400000);
  if (d.toDateString() === y.toDateString()) return '昨天';
  return (d.getMonth() + 1) + '月' + d.getDate() + '日';
}

function renderPanel() {
  const titles = { write: '写作', skills: '技能', project: '档案', book: '书稿', corpus: '语料' };
  const t = $('#panelTitle');
  if (t) t.textContent = titles[S.view] || '写作';
  if (S.view === 'book') return renderBookPanel();
  if (S.view === 'skills') return renderSkillList();
  if (S.view === 'project') return renderProjectPanel();
  if (S.view === 'corpus') return renderCorpusPanel();
  return renderConvs();
}

function wfPanelHtml() {
  const wf = currentWorkflow();
  if (!wf) return '';
  const n = wf.steps.length;
  let h = '<div class="wf-now"><div class="wn-head">' + esc(wf.name) +
    '<span>' + (Math.min(S.wfStep, n - 1) + 1) + '/' + n + '</span></div>';
  wf.steps.forEach((st, i) => {
    h += '<div class="wn-step' + (i === S.wfStep ? ' on' : '') + (i < S.wfStep ? ' done' : '') +
      '" data-wfstep="' + i + '"><i>' + (i < S.wfStep ? '✓' : (i + 1)) + '</i>' +
      esc(st.name) + '</div>';
  });
  h += '<div class="wn-exit" id="wnExit">退出工作流</div></div>';
  return h;
}

function renderConvs() {
  if (S.view !== 'write') return;
  const body = $('#panelBody');
  if (!body) return;
  const wfHtml = wfPanelHtml();
  if (!S.convs.length) {
    body.innerHTML = wfHtml + (wfHtml
      ? '<div class="panel-empty" style="padding:14px 10px">这个工作流还没有对话。<br>直接发第一条消息就会开始。</div>'
      : '<div class="panel-empty">还没有作品。<br>点右上角的 + 开始写。</div>');
    bindWfPanel(body);
    return;
  }
  const groups = {};
  S.convs.forEach(c => {
    const k = (c.projectTitle || '').trim() || '未归档';
    (groups[k] = groups[k] || []).push(c);
  });
  let html = '';
  Object.keys(groups).forEach(k => {
    html += '<div class="conv-group">' + esc(k) + '</div>';
    groups[k].forEach(c => {
      const wfTag = c.workflowId
        ? '<span class="conv-wf">' + esc(wfName(c.workflowId)) + '</span>' : '';
      html += '<div class="conv' + (S.current && S.current.id === c.id ? ' active' : '') + '" data-id="' + c.id + '">' +
        '<div class="conv-title">' + wfTag + esc(c.title || '未命名创作') + '</div>' +
        '<div class="conv-meta"><span>' + fmtTime(c.updatedAt) + '</span><i></i><span>' +
        (c.messageCount || 0) + ' 条</span></div>' +
        '<button class="conv-del" title="删除">×</button></div>';
    });
  });
  body.innerHTML = wfHtml + html;
  bindWfPanel(body);
  body.querySelectorAll('.conv').forEach(el => {
    el.onclick = (e) => {
      if (e.target.classList.contains('conv-del')) return;
      openConv(el.dataset.id);
    };
    el.querySelector('.conv-del').onclick = async (e) => {
      e.stopPropagation();
      const c = S.convs.find(x => x.id === el.dataset.id) || {};
      if (!confirm('删除「' + (c.title || '未命名创作') + '」？此操作不可撤销。')) return;
      await api('DELETE', '/api/conversations/' + el.dataset.id);
      S.convs = S.convs.filter(x => x.id !== el.dataset.id);
      if (S.current && S.current.id === el.dataset.id) {
        S.current = null;
        renderThread();
        renderInspector();
      }
      renderPanel();
      toast('已删除');
    };
  });
}

function bindWfPanel(body) {
  body.querySelectorAll('[data-wfstep]').forEach(el => {
    el.onclick = () => goWorkflowStep(+el.dataset.wfstep);
  });
  const x = $('#wnExit');
  if (x) x.onclick = exitWorkflow;
}

function renderSkillList() {
  const body = $('#panelBody');
  if (!body) return;
  const groups = {};
  S.skills.forEach(s => (groups[s.category] = groups[s.category] || []).push(s));
  let html = '';
  Object.keys(groups).forEach(g => {
    html += '<div class="conv-group">' + esc(g) + '</div>';
    groups[g].forEach(s => {
      html += '<div class="skill-item' + (s.id === S.skillId ? ' active' : '') + '" data-skill="' + s.id +
        '" style="--c:' + (s.accent || 'var(--accent)') + '">' +
        '<div class="si-top"><span class="si-name">' + esc(s.name) + '</span>' +
        '<span class="si-tag">' + esc(s.tag || '') + '</span></div>' +
        '<div class="si-desc">' + esc(SKILL_DESC[s.id] || '') + '</div>' +
        (s.editable ? '<button class="si-del" data-del-skill="' + s.id + '" title="删除这个导入的技能">×</button>' : '') +
        '</div>';
    });
  });
  let wfHtml = '';
  if (typeof WORKFLOWS !== 'undefined' && WORKFLOWS.length) {
    wfHtml = '<div class="conv-group">工作流</div>';
    WORKFLOWS.forEach(w => {
      wfHtml += '<div class="wf-card' + (S.workflow === w.id ? ' active' : '') +
        '" data-wf="' + w.id + '" style="--c:' + (w.accent || 'var(--accent)') + '">' +
        '<div class="wc-top"><span class="wc-name">' + esc(w.name) + '</span>' +
        '<span class="wc-n">' + w.steps.length + ' 步</span></div>' +
        '<div class="wc-desc">' + esc(w.desc) + '</div>' +
        '<div class="wc-dots">' + w.steps.map(() => '<i></i>').join('') + '</div></div>';
    });
  }
  body.innerHTML = '<input class="panel-search" id="skillSearch" placeholder="搜索技能或工作流…" autocomplete="off" spellcheck="false">' +
    wfHtml + html;
  body.querySelectorAll('[data-wf]').forEach(el => {
    el.onclick = () => startWorkflow(el.dataset.wf);
  });
  body.querySelectorAll('[data-skill]').forEach(el => {
    el.onclick = (e) => {
      if (e.target.dataset && e.target.dataset.delSkill) return;
      pickSkill(el.dataset.skill);
    };
  });
  body.querySelectorAll('[data-del-skill]').forEach(b => {
    b.onclick = async (e) => {
      e.stopPropagation();
      const id = b.dataset.delSkill;
      const sk = S.skills.find(x => x.id === id);
      if (!confirm('删除导入的技能「' + (sk ? sk.name : id) + '」？')) return;
      try {
        const r = await api('DELETE', '/api/skills/' + encodeURIComponent(id));
        S.skills = r.skills;
        if (S.skillId === id) S.skillId = S.skills[0].id;
        renderSkillList();
        renderSkill();
        toast('已删除');
      } catch (err) { toast(err.message); }
    };
  });
  const q = $('#skillSearch');
  if (q) q.oninput = () => {
    const k = q.value.trim().toLowerCase();
    body.querySelectorAll('.skill-item, .wf-card').forEach(el => {
      el.style.display = (!k || el.textContent.toLowerCase().includes(k)) ? '' : 'none';
    });
    body.querySelectorAll('.conv-group').forEach(g => {
      let n = g.nextElementSibling, any = false;
      while (n && !n.classList.contains('conv-group')) {
        if (n.classList.contains('skill-item') && n.style.display !== 'none') { any = true; break; }
        n = n.nextElementSibling;
      }
      g.style.display = any ? '' : 'none';
    });
  };
}

function renderProjectPanel() {
  const body = $('#panelBody');
  if (!body) return;
  const p = S.project || {};
  const rows = PROJECT_FIELDS.filter(([k]) => (p[k] || '').trim());
  let html = '<div class="panel-pad">';
  if (!rows.length) {
    html += '<div class="panel-empty">档案还是空的。<br>填了之后，每轮对话都会带上。</div>';
  } else {
    rows.forEach(([k, label]) => {
      html += '<div class="brief"><div class="brief-k">' + label + '</div><div class="brief-v">' +
        esc((p[k] || '').slice(0, 90)) + '</div></div>';
    });
  }
  html += '<button class="ghost" id="panelEditProject" style="margin-top:10px;border-color:var(--line);width:100%;justify-content:center">编辑创作档案</button></div>';
  body.innerHTML = html;
  const b = $('#panelEditProject');
  if (b) b.onclick = () => $('#btnProject').click();
}

function renderInspector() {
  if (S.view === 'book') return renderBookInspector();
  const p = S.project || {};
  const el = $('#inspProject');
  if (!el) return;
  el.textContent = (p.title || '').trim() || (S.current ? (S.current.title || '未命名') : '未命名');
  $('#inspGenre').textContent = [p.genre, p.audience].filter(Boolean).join(' · ') || '还没有设定类型';

  const msgs = (S.current && S.current.messages) || [];
  const chars = msgs.reduce((n, m) => n + ((m.content || '').replace(/\s/g, '').length), 0);
  const prov = (S.config.providers || []).find(x => x.id === S.config.activeProviderId);
  const sk = currentSkill();
  const sc = (S.current && S.current.summaryCount) || 0;
  const ctx = msgs.slice(sc).reduce((n, m) => n + ((m.content || '').length), 0) +
    ((S.current && S.current.summary) ? S.current.summary.length : 0);
  const rows = [
    ['字数', chars ? chars.toLocaleString() : '0'],
    ['消息', String(msgs.length)],
    ['上下文', ctx ? fmtK(ctx) + (sc ? ' · 已压缩' : '') : '—'],
    ['素材', ((S.current && S.current.materials) || []).length
      ? (S.current.materials.length + ' 份') : '—'],
    ['技能', sk ? sk.name : '—'],
    ['模型', prov ? (prov.model || '未选') : '未配置'],
  ];
  $('#inspStats').innerHTML = rows.map(([k, v]) =>
    '<div class="stat-row"><span>' + k + '</span><span>' + esc(v) + '</span></div>').join('');

  renderTrainerCard();

  const brief = PROJECT_FIELDS.filter(([k]) => (p[k] || '').trim()).slice(0, 3);
  $('#inspBrief').innerHTML = brief.length
    ? brief.map(([k, label]) => '<div class="brief"><div class="brief-k">' + label + '</div><div class="brief-v">' +
      esc((p[k] || '').slice(0, 56)) + '</div></div>').join('')
    : '<div class="insp-sub">填了创作档案后会显示在这里。</div>';
}

/* ---------------------------------------------------------- 语料库 */
const CORPUS = { data: null, log: [], report: '', poll: 0 };

async function loadCorpus() {
  try { CORPUS.data = await api('GET', '/api/corpus/overview'); }
  catch (e) { CORPUS.data = null; }
  return CORPUS.data;
}

function csCard(k, v, s) {
  return '<div class="cs-card"><div class="cs-k">' + k + '</div><div class="cs-v">' + v + '</div>' +
    (s ? '<div class="cs-s">' + s + '</div>' : '') + '</div>';
}

function renderCorpusPanel() {
  const body = $('#panelBody');
  if (!body) return;
  const books = (CORPUS.data || {}).books || [];
  let h = '<div class="corpus-acts">' +
    '<button class="corpus-btn" data-cact="import">导入 .txt / .md</button>' +
    '<button class="corpus-btn" data-cact="style">统计文风</button>' +
    '<button class="corpus-btn" data-cact="plan">排蒸馏任务</button>' +
    '<button class="corpus-btn primary" data-cact="run">开始蒸馏</button>' +
    '</div><div class="corpus-list">';
  if (!books.length) h += '<div class="panel-empty">还没有书。<br>点「导入」选几个 txt。</div>';
  books.forEach(b => {
    h += '<div class="corpus-item"><div class="ci-t">' + esc(b.title) + '</div>' +
      '<div class="ci-m">' + esc(b.genre || '未分类') + ' · ' +
      (b.words / 10000).toFixed(1) + ' 万字 · ' + b.chapters + ' 章</div></div>';
  });
  h += '</div>';
  body.innerHTML = h;
  body.querySelectorAll('[data-cact]').forEach(el => el.onclick = () => corpusAction(el.dataset.cact));
}

function renderCorpusView() {
  const el = $('#corpusBody');
  if (!el) return;
  const d = CORPUS.data || {};
  const ov = d.overview || {};
  const jobs = ov.jobs || {};
  let h = '<div class="corpus-cards">' +
    csCard('书目', (ov.books || 0) + ' 本', (ov.chapters || 0) + ' 章') +
    csCard('总字数', ((ov.words || 0) / 10000).toFixed(1) + ' 万') +
    csCard('已蒸馏', (ov.distilled || 0) + ' 章', '待跑 ' + (jobs.todo || 0)) +
    csCard('失败', (jobs.dead || 0) + ' 章', '重试 3 次后放弃') +
    '</div>' +
    '<div class="corpus-search"><input class="input" id="corpusQ" placeholder="跨书检索：人名、地名、任何片段">' +
    '<button class="corpus-btn" id="btnCorpusSearch">搜索</button></div>' +
    '<div id="corpusResult" class="corpus-result"></div>';
  if (CORPUS.log.length) {
    h += '<div class="corpus-log"><div class="cl-h">蒸馏进度</div>' +
      CORPUS.log.slice(-14).map(x => '<div class="cl-l">' + esc(x) + '</div>').join('') + '</div>';
  }
  if (CORPUS.report) {
    h += '<pre class="corpus-report">' + esc(CORPUS.report) + '</pre>';
  } else {
    h += '<div class="corpus-hint">左边可以导入书稿、统计文风、排任务、开始蒸馏。<br>' +
      '蒸馏会逐章调用当前配置的模型，跑之前会先报预算。</div>';
  }
  el.innerHTML = h;
  const btn = $('#btnCorpusSearch');
  if (btn) btn.onclick = corpusSearch;
  const q = $('#corpusQ');
  if (q) q.onkeydown = e => { if (e.key === 'Enter') corpusSearch(); };
}

async function corpusSearch() {
  const q = ($('#corpusQ') || {}).value || '';
  const box = $('#corpusResult');
  if (!box) return;
  if (!q.trim()) { box.innerHTML = ''; return; }
  box.innerHTML = '<div class="corpus-hint">检索中…</div>';
  try {
    const d = await api('GET', '/api/corpus/search?q=' + encodeURIComponent(q));
    const hits = d.hits || [];
    box.innerHTML = hits.length
      ? hits.map(hh => '<div class="corpus-hit"><div class="ch-t">第' + hh.no + '章 ' +
          esc(hh.title) + '</div><div class="ch-s">' + esc(hh.snippet) + '</div></div>').join('')
      : '<div class="corpus-hint">没找到。</div>';
  } catch (e) {
    box.innerHTML = '<div class="corpus-hint">检索失败：' + esc(e.message) + '</div>';
  }
}

function corpusImport() {
  const inp = document.createElement('input');
  inp.type = 'file';
  inp.accept = '.txt,.md';
  inp.multiple = true;
  inp.onchange = async () => {
    const files = Array.from(inp.files || []);
    if (!files.length) return;
    let ok = 0, bad = 0;
    for (const f of files) {
      try {
        const r = await api('POST', '/api/corpus/import', { name: f.name, text: await f.text() });
        if (r && r.ok) ok++; else bad++;
      } catch (e) { bad++; }
    }
    toast('导入 ' + ok + ' 本' + (bad ? '，失败 ' + bad : ''));
    await loadCorpus();
    renderCorpusPanel(); renderCorpusView();
  };
  inp.click();
}

async function corpusAction(kind) {
  if (kind === 'import') return corpusImport();
  try {
    if (kind === 'style') {
      const r = await api('POST', '/api/corpus/style', {});
      toast('已统计 ' + r.count + ' 本文风指标');
    } else if (kind === 'plan') {
      const r = await api('POST', '/api/corpus/plan', { plan: 'sample' });
      toast('已排 ' + r.planned + ' 个任务');
      await loadCorpus();
    } else if (kind === 'run') {
      const est = await api('POST', '/api/corpus/estimate', {});
      if (!est.jobs) { toast('没有待办任务，先排任务'); return; }
      const go = confirm('待跑 ' + est.jobs + ' 章\n\n输入约 ' +
        (est.tokensIn / 10000).toFixed(1) + ' 万 token，输出约 ' +
        (est.tokensOut / 10000).toFixed(1) + ' 万 token\n并发 4，约 ' +
        est.minutes + ' 分钟\n\n开始蒸馏？');
      if (!go) return;
      const r = await api('POST', '/api/corpus/run', { concurrency: 4 });
      if (!r.ok) { toast(r.error || '启动失败'); return; }
      CORPUS.log = [];
      toast('开始蒸馏，共 ' + r.estimate.jobs + ' 章');
      corpusPoll();
    }
  } catch (e) { toast(e.message); }
  renderCorpusPanel();
  renderCorpusView();
}

function corpusPoll() {
  clearTimeout(CORPUS.poll);
  CORPUS.poll = setTimeout(async () => {
    try {
      const p = await api('GET', '/api/corpus/progress');
      CORPUS.log = p.log || [];
      renderCorpusView();
      if (p.running) return corpusPoll();
      await loadCorpus();
      renderCorpusPanel(); renderCorpusView();
      toast('蒸馏结束：成功 ' + p.done + ' / 失败 ' + p.failed);
    } catch (e) { /* 轮询失败静默，下一轮再说 */ }
  }, 1200);
}

async function corpusReport() {
  try {
    const d = await api('GET', '/api/corpus/report');
    CORPUS.report = d.markdown || '';
    renderCorpusView();
    toast('报告已生成');
  } catch (e) { toast(e.message); }
}

function setView(v) {
  S.view = v;
  try { localStorage.setItem('inkstone.view', v); } catch (_) { }
  $$('.rail-btn[data-view]').forEach(b => b.classList.toggle('on', b.dataset.view === v));
  const add = $('#btnNew'), imp = $('#btnImportSkill'), bl = $('#btnBookList');
  if (add) add.classList.toggle('hidden', v === 'skills');
  if (imp) imp.classList.toggle('hidden', v !== 'skills');
  if (bl) bl.classList.toggle('hidden', v !== 'book');
  const vw = $('#viewWrite'), vb = $('#viewBook'), vc = $('#viewCorpus');
  if (vw) vw.classList.toggle('hidden', v === 'book' || v === 'corpus');
  if (vb) vb.classList.toggle('hidden', v !== 'book');
  if (vc) vc.classList.toggle('hidden', v !== 'corpus');
  const app = $('#app');
  if (app) app.classList.toggle('book-mode', v === 'book');
  if (app) app.classList.toggle('corpus-mode', v === 'corpus');
  if (v === 'corpus') {
    loadCorpus().then(() => { renderCorpusView(); renderCorpusPanel(); });
  }
  if (v === 'book') {
    loadBooks().then(() => {
      if (!BK.book && BK.list.length) openBook(BK.list[0].id);
      else {
        setBookHeader('', true);
        showChapterEmpty();
        renderBookPanel();
        renderBookInspector();
      }
    });
  }
  renderPanel();
  renderInspector();
}

async function openConv(id) {
  try {
    const c = await api('GET', '/api/conversations/' + id);
    S.current = c;
    S.skillId = c.skillId || S.skillId;
    S.project = c.project || {};
    S.workflow = c.workflowId || null;
    S.wfStep = c.workflowStep || 0;
    if (S.view !== 'write') setView('write');
    renderSkill();
    renderThread();
    renderMaterials();
    renderPanel();
    renderInspector();
    scrollBottom();
    $('#panel').classList.remove('open');
  } catch (e) { toast(e.message); }
}

async function newConv() {
  S.current = null;
  S.workflow = null;
  S.wfStep = 0;
  renderMaterials();
  if (S.view !== 'write') setView('write');
  S.project = {};
  renderThread();
  renderPanel();
  renderInspector();
  $('#input').focus();
  $('#panel').classList.remove('open');
}

/* ---------------------------------------------------------- 线程渲染 */
function heroEl() {
  const wrap = document.createElement('div');
  wrap.className = 'empty';
  wrap.innerHTML = '<div class="empty-mark">砚</div>' +
    '<h2>把想法，写成作品。</h2>' +
    '<p>从左侧挑一个技能开始，或直接在下面写 · ' +
    '<button class="link-btn" id="heroTheme">换主题</button></p>';
  const ht = wrap.querySelector('#heroTheme');
  if (ht) ht.onclick = () => openSettings('look');
  return wrap;
}

function summaryEl(c) {
  const d = document.createElement('details');
  d.className = 'ctx-note';
  d.innerHTML = '<summary>前情提要 · 已压缩 ' + (c.summaryCount || 0) +
    ' 条早期消息</summary><div class="ctx-body">' + esc(c.summary) + '</div>';
  return d;
}

function msgEl(msg, idx) {
  if (msg.role === 'user') {
    const d = document.createElement('div');
    d.className = 'msg user';
    d.innerHTML = '<div class="msg-head"><span>我</span></div><div class="msg-body"></div>';
    d.querySelector('.msg-body').textContent = msg.content;
    return d;
  }
  const d = document.createElement('div');
  d.className = 'msg assistant' + (msg.error ? ' error' : '');
  const sk = S.skills.find(s => s.id === msg.skillId) || currentSkill();
  const head = document.createElement('div');
  head.className = 'msg-head';
  head.innerHTML = '<span class="badge"><i style="background:' + (sk ? sk.accent : '#B23A2F') + '"></i>' +
    esc(sk ? sk.name : '砚') + '</span>';
  const body = document.createElement('div');
  body.className = 'msg-body md';
  body.innerHTML = msg.error ? esc(msg.content || msg.error) : md(msg.content || '');
  d.appendChild(head);
  d.appendChild(body);
  if (!msg.error) d.appendChild(extrasEl(msg, idx));
  return d;
}

function renderThread() {
  const thread = $('#thread');
  thread.innerHTML = '';
  const msgs = (S.current && S.current.messages) || [];
  if (!msgs.length) { thread.appendChild(heroEl()); return; }
  if (S.current && S.current.summary) thread.appendChild(summaryEl(S.current));
  msgs.forEach((m, i) => thread.appendChild(msgEl(m, i)));
  scrollBottom();
}

/* ---------------------------------------------------------- 发送 */
function autosize() {
  const ta = $('#input');
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 260) + 'px';
}

function setStreaming(on) {
  S.streaming = on;
  $('#btnSend').disabled = on;
  $('#btnStop').classList.toggle('hidden', !on);
  $('#hint').textContent = on ? '生成中… 可随时停止' : 'Enter 发送 · Shift + Enter 换行 · / 指令';
  $$('#stages .stage').forEach(b => b.style.opacity = on ? .5 : 1);
}

function appendLive() {
  const thread = $('#thread');
  const d = document.createElement('div');
  d.className = 'msg assistant';
  const sk = currentSkill();
  d.innerHTML = '<div class="msg-head"><span class="badge"><i style="background:' +
    (sk ? sk.accent : '#B23A2F') + '"></i>' + esc(sk ? sk.name : '砚') + '</span></div>' +
    '<div class="msg-body md"></div>';
  thread.appendChild(d);
  S.live = { node: d, body: d.querySelector('.msg-body'), text: '', cont: false };
  scrollBottom();
  return S.live;
}

let paintPending = false;
function pushDelta(t) {
  if (!S.live) return;
  S.live.text += t;
  if (paintPending) return;
  paintPending = true;
  requestAnimationFrame(() => {
    paintPending = false;
    if (!S.live) return;
    const stick = nearBottom();
    S.live.body.innerHTML = md(S.live.text) + '<span class="caret"></span>';
    if (stick) scrollBottom();
  });
}

/* 截断 / 中断 / 操作按钮，统一挂在一条 .msg-extra 里，方便重绘时清理 */
function extrasEl(msg, idx) {
  const wrap = document.createElement('div');
  wrap.className = 'msg-extra';

  if (msg.truncated || msg.incomplete) {
    const note = document.createElement('div');
    note.className = 'trunc-note';
    const span = document.createElement('span');
    if (msg.truncated) {
      span.textContent = msg.limit
        ? '输出达到上限（' + msg.limit + ' tokens），内容被截断'
        : '输出达到上限，内容被截断';
    } else {
      span.textContent = '生成中断，已保留前半部分';
    }
    const btn = document.createElement('button');
    btn.textContent = '继续写';
    btn.onclick = () => continueWriting();
    note.appendChild(span);
    note.appendChild(btn);
    wrap.appendChild(note);
  }

  wrap.appendChild(actionsEl(msg, idx));
  return wrap;
}

function actionsEl(msg, idx) {
  const box = document.createElement('div');
  box.className = 'msg-actions';
  const copy = document.createElement('button');
  copy.textContent = '复制';
  copy.onclick = async () => {
    try { await navigator.clipboard.writeText(msg.content); toast('已复制'); }
    catch (e) { toast('复制失败'); }
  };
  box.appendChild(copy);

  const isLast = S.current && idx === (S.current.messages || []).length - 1;
  if (isLast) {
    const cont = document.createElement('button');
    cont.textContent = '继续写';
    cont.onclick = () => continueWriting();
    box.appendChild(cont);

    const re = document.createElement('button');
    re.textContent = '重新生成';
    re.onclick = () => send(true);
    box.appendChild(re);
  }

  const wc = document.createElement('button');
  wc.textContent = (msg.content || '').replace(/\s/g, '').length + ' 字';
  wc.style.cursor = 'default';
  wc.onclick = null;
  box.appendChild(wc);
  return box;
}

function finishLive(meta) {
  if (!S.live) return null;
  const live = S.live;
  S.live = null;
  live.body.innerHTML = md(live.text);

  const cont = !!(meta && meta.cont);
  let msg;
  if (cont) {
    msg = S.current.messages[S.current.messages.length - 1];
    if (!msg) return null;
  } else {
    msg = { role: 'assistant', content: '', skillId: S.skillId, ts: Date.now() / 1000 };
    S.current.messages.push(msg);
  }
  msg.content = live.text;
  msg.finish = (meta && meta.finish) || 'stop';
  msg.truncated = !!(meta && meta.truncated);
  msg.incomplete = !!(meta && meta.incomplete);
  if (meta && meta.limit) msg.limit = meta.limit;

  live.node.querySelectorAll('.msg-extra').forEach(n => n.remove());
  live.node.appendChild(extrasEl(msg, S.current.messages.length - 1));
  return msg;
}

function failLive(message) {
  const live = S.live;
  S.live = null;
  if (live && live.text) {
    // 有半截内容就留下，并给一个「继续写」的出口
    live.body.innerHTML = md(live.text);
    let msg;
    if (live.cont) {
      msg = S.current.messages[S.current.messages.length - 1];
    } else {
      msg = { role: 'assistant', content: '', skillId: S.skillId, ts: Date.now() / 1000 };
      S.current.messages.push(msg);
    }
    if (msg) {
      msg.content = live.text;
      msg.incomplete = true;
      live.node.querySelectorAll('.msg-extra').forEach(n => n.remove());
      const strip = document.createElement('div');
      strip.className = 'err-strip';
      strip.textContent = '生成中断：' + message;
      live.node.appendChild(strip);
      live.node.appendChild(extrasEl(msg, S.current.messages.length - 1));
    }
    return;
  }
  if (live) live.node.remove();
  const thread = $('#thread');
  const d = document.createElement('div');
  d.className = 'msg assistant error';
  d.innerHTML = '<div class="msg-head"><span class="badge"><i style="background:var(--accent)"></i>出错了</span></div>' +
    '<div class="msg-body md"></div>';
  d.querySelector('.msg-body').textContent = message;
  thread.appendChild(d);
  scrollBottom();
}

/* 读 SSE 流，返回 {ok, done} */
async function consumeStream(res, cont) {
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let finished = false;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let ev = 'message';
      let data = '';
      block.split('\n').forEach(line => {
        if (line.startsWith('event:')) ev = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      });
      if (!data) continue;
      let obj = {};
      try { obj = JSON.parse(data); } catch (e) { continue; }

      if (ev === 'meta') {
        if (obj.title && S.current) S.current.title = obj.title;
        if (obj.conversationId && S.current && !S.current.id) S.current.id = obj.conversationId;
      } else if (ev === 'delta') {
        pushDelta(obj.text || '');
      } else if (ev === 'error') {
        finished = true;
        failLive(obj.message || '生成失败');
        return { ok: false };
      } else if (ev === 'done') {
        finished = true;
        finishLive({
          cont,
          finish: obj.finish,
          truncated: obj.truncated,
          incomplete: obj.incomplete,
          limit: obj.limit,
        });
        // 会话是第一条消息才建的，这时才存得下工作流状态
        if (S.workflow) saveWorkflow();
        return { ok: true };
      }
    }
  }
  if (!finished) {
    // 服务端没发 done 就断开了：把已有的内容当半成品收下
    if (S.live) finishLive({ cont, finish: 'interrupted', incomplete: true });
    return { ok: false, interrupted: true };
  }
  return { ok: true };
}

function checkModel() {
  const prov = (S.config.providers || []).find(p => p.id === S.config.activeProviderId);
  if (!prov) { toast('请先在设置里配置模型'); openSettings('model'); return null; }
  const isLocal = prov.kind === 'ollama' || /localhost|127\.0\.0\.1/.test(prov.baseUrl || '');
  if (!prov.apiKey && !isLocal) { toast('这个服务商还没填 API Key'); openSettings('model'); return null; }
  if (!prov.model) { toast('请先选择模型名称'); openSettings('model'); return null; }
  return prov;
}

async function send(regenerate) {
  if (S.streaming) return;
  const ta = $('#input');
  const text = ta.value.trim();
  if (!regenerate && !text) return;

  if (!regenerate && text.startsWith('/')) {
    const hit = COMMANDS.find(c => c.key === text || c.alias === text);
    if (hit) { runCommand(hit); return; }
  }
  if (!checkModel()) return;

  if (!S.current) {
    try {
      S.current = await api('POST', '/api/conversations', { skillId: S.skillId });
      S.project = S.current.project || {};
    } catch (e) { toast(e.message); return; }
  }

  if (regenerate) {
    while (S.current.messages.length && S.current.messages[S.current.messages.length - 1].role === 'assistant') {
      S.current.messages.pop();
    }
    if (!S.current.messages.length) return;
  } else {
    S.current.messages.push({ role: 'user', content: text });
    ta.value = '';
    autosize();
  }

  renderThread();
  appendLive();
  setStreaming(true);
  S.ctrl = new AbortController();

  const payload = {
    conversationId: S.current.id,
    skillId: S.skillId,
    content: text,
    project: S.project,
    regenerate: !!regenerate,
    providerId: S.config.activeProviderId,
  };

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: S.ctrl.signal,
    });
    if (!res.ok || !res.body) {
      const t = await res.text().catch(() => '');
      throw new Error(t || ('HTTP ' + res.status));
    }
    const r = await consumeStream(res, false);
    if (r.interrupted) toast('连接中断，已保留已生成的内容');
    await refreshConvs();
  } catch (e) {
    if (e.name === 'AbortError') {
      if (S.live && S.live.text) { finishLive({ cont: false, finish: 'stopped' }); toast('已停止'); }
      else if (S.live) { S.live.node.remove(); S.live = null; }
    } else {
      failLive(e.message || '请求失败');
    }
  } finally {
    setStreaming(false);
    S.ctrl = null;
    renderPanel();
    renderInspector();
  }
}

/* 续写：把新内容接在最后一条回复后面，而不是另起一条 */
async function continueWriting() {
  if (S.streaming || !S.current) return;
  const msgs = S.current.messages || [];
  const last = msgs[msgs.length - 1];
  if (!last || last.role !== 'assistant') { toast('没有可续写的内容'); return; }
  if (!checkModel()) return;

  const nodes = $$('#thread .msg.assistant');
  const node = nodes[nodes.length - 1];
  if (!node) return;
  const body = node.querySelector('.msg-body');
  node.querySelectorAll('.msg-extra').forEach(n => n.remove());
  body.innerHTML = md(last.content) + '<span class="caret"></span>';
  S.live = { node, body, text: last.content, cont: true };
  setStreaming(true);
  S.ctrl = new AbortController();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversationId: S.current.id,
        skillId: S.skillId,
        project: S.project,
        continue: true,
        providerId: S.config.activeProviderId,
      }),
      signal: S.ctrl.signal,
    });
    if (!res.ok || !res.body) {
      const t = await res.text().catch(() => '');
      throw new Error(t || ('HTTP ' + res.status));
    }
    const r = await consumeStream(res, true);
    if (r.interrupted) toast('连接中断，已保留已生成的内容');
    await refreshConvs();
  } catch (e) {
    if (e.name === 'AbortError') {
      if (S.live && S.live.text) { finishLive({ cont: true, finish: 'stopped' }); toast('已停止'); }
      else if (S.live) { S.live = null; }
    } else {
      failLive(e.message || '请求失败');
    }
  } finally {
    setStreaming(false);
    S.ctrl = null;
    renderPanel();
    renderInspector();
  }
}

async function refreshConvs() {
  try {
    const d = await api('GET', '/api/conversations');
    S.convs = d.conversations || [];
    renderPanel();
    renderInspector();
  } catch (e) { }
}

/* ---------------------------------------------------------- 模型状态 */
function updateModelChip() {
  const prov = (S.config.providers || []).find(p => p.id === S.config.activeProviderId);
  const dot = $('#modelDot');
  const name = $('#modelName');
  const foot = $('#footNote');
  if (!prov) {
    name.textContent = '未配置模型 · 点此设置';
    dot.classList.remove('on');
    foot.textContent = '支持 OpenAI / Claude / DeepSeek / 通义 / 本地 Ollama';
    return;
  }
  const isLocal = prov.kind === 'ollama' || /localhost|127\.0\.0\.1/.test(prov.baseUrl || '');
  const ready = !!(prov.apiKey || isLocal);
  dot.classList.toggle('on', ready);
  name.textContent = ready ? prov.name + ' · ' + (prov.model || '未选模型') : '未配置模型 · 点此设置';
  foot.textContent = !ready
    ? '支持 OpenAI / Claude / DeepSeek / 通义 / 本地 Ollama · 密钥只存本机'
    : isLocal
      ? '本地模型 · ' + (prov.baseUrl || '') + ' · 内容不出本机'
      : '云端模型 · 请求经 ' + (prov.name || '') + ' · 密钥仅存本机';
}


/* ---------------------------------------------------------- 训练家卡 */
const TC_AVATAR = '<img src="/static/assets/avatar.png" alt="">';

const TC_CAP = '<svg viewBox="0 0 24 24" shape-rendering="crispEdges">' +
  '<rect x="4" y="8" width="16" height="7" fill="#C0392B"/>' +
  '<rect x="2" y="14" width="20" height="3" fill="#96291D"/>' +
  '<rect x="10" y="5" width="5" height="3" fill="#E04B3A"/>' +
  '</svg>';

const TC_BALL = '<svg viewBox="0 0 24 24">' +
  '<circle cx="12" cy="12" r="9" fill="#F6ECD4" stroke="#2E2622" stroke-width="2"/>' +
  '<path d="M3.6 12a8.4 8.4 0 0 1 16.8 0z" fill="#E04B3A"/>' +
  '<rect x="3" y="10.8" width="18" height="2.6" fill="#2E2622"/>' +
  '<circle cx="12" cy="12" r="3" fill="#F6ECD4" stroke="#2E2622" stroke-width="2"/>' +
  '</svg>';

function renderTrainerCard() {
  const box = $('#trainerCard');
  if (!box) return;
  const theme = (S.config && S.config.appearance && S.config.appearance.theme) || 'paper';
  const on = theme === 'trainer';
  box.classList.toggle('hidden', !on);
  if (!on) return;

  const p = S.project || {};
  const msgs = (S.current && S.current.messages) || [];
  const chars = msgs.reduce((n, m) => n + ((m.content || '').replace(/\s/g, '').length), 0);
  const filled = PROJECT_FIELDS.filter(([k]) => (p[k] || '').trim()).length;

  const bars = [
    ['字', '字数', chars, 100000],
    ['章', '章节', S.convs.length, 100],
    ['信', '消息', msgs.length, 500],
    ['设', '设定', filled, PROJECT_FIELDS.length],
  ].map(row => {
    const ico = row[0], label = row[1], val = row[2], target = row[3];
    const pct = Math.min(100, Math.round(val / target * 100));
    return '<div class="tc-stat"><span class="ico">' + ico + '</span>' +
      '<span style="width:24px">' + label + '</span>' +
      '<span class="bar"><i style="width:' + pct + '%"></i></span>' +
      '<span class="num">' + val + '</span></div>';
  }).join('');

  const name = (p.title || '').trim() || '无名训练家';
  const lv = Math.min(99, 1 + Math.floor(chars / 2000));

  box.innerHTML =
    '<div class="tc-head"><b>训练家</b><span>' + esc(name) + ' Lv.' + lv + '</span></div>' +
    '<div class="tc-avatar">' + TC_AVATAR + '</div>' + bars +
    '<div class="tc-badges"><span class="tc-badge">' + TC_CAP + '</span>' +
    '<span class="tc-badge">' + TC_BALL + '</span></div>';
}

/* ---------------------------------------------------------- 外观 */
function applyAppearance() {
  const a = (S.config && S.config.appearance) || {};
  const bg = (S.bgs || []).find(b => b.id === a.backgroundId);
  applyTheme(a, bg ? bg.url : null);
  renderTrainerCard();
}

async function uploadBg(file) {
  if (!file) return;
  if (file.size > 16 * 1024 * 1024) { toast('图片请小于 16MB'); return; }
  const dataUrl = await new Promise((res, rej) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.onerror = rej;
    fr.readAsDataURL(file);
  });
  try {
    const d = await api('POST', '/api/backgrounds', { dataUrl, name: file.name });
    S.bgs.unshift(d.background);
    const cfg = JSON.parse(JSON.stringify(S.config));
    cfg.appearance.backgroundId = d.background.id;
    if (!cfg.appearance.intensity) cfg.appearance.intensity = 0.6;
    const r = await api('POST', '/api/config', cfg);
    S.config = r.config;
    applyAppearance();
    if ($('#modal').classList.contains('show') && curTab === 'look') renderTab();
    toast('背景已应用');
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------- 档案 */
function renderProject() {
  const box = $('#projectForm');
  $('#drawerTitle').textContent = '创作档案';
  $('#drawerSub').textContent = '这里填的内容会注入每一轮对话，作为本书的唯一事实来源。';
  $('#drawerActs').innerHTML = DRAWER_DEFAULT_ACTS;
  const clr = $('#btnClearProject');
  if (clr) clr.onclick = () => {
    if (!confirm('清空本作品的创作档案？')) return;
    S.project = {};
    renderProject();
    saveProject();
  };
  if (!S.current) {
    box.innerHTML = '<div style="font-size:12px;color:var(--muted);line-height:1.8;padding:20px 0">' +
      '先开始一次创作，再来填档案。<br>档案会随每次对话一起发送给模型。</div>';
    return;
  }
  let html = '';
  PROJECT_FIELDS.forEach(([k, label, type, ph]) => {
    const v = (S.project && S.project[k]) || '';
    html += '<div class="field"><label>' + label + '</label>';
    if (type === 'input') {
      html += '<input class="input" data-p="' + k + '" value="' + esc(v) + '" placeholder="' + esc(ph) + '">';
    } else {
      html += '<textarea class="textarea" data-p="' + k + '" placeholder="' + esc(ph) + '">' + esc(v) + '</textarea>';
    }
    html += '</div>';
  });
  box.innerHTML = html;
  box.querySelectorAll('[data-p]').forEach(inp => {
    inp.addEventListener('input', () => {
      S.project[inp.dataset.p] = inp.value;
      $('#saveState').textContent = '编辑中…';
      $('#saveState').classList.remove('saved');
      clearTimeout(S.projectTimer);
      S.projectTimer = setTimeout(saveProject, 700);
    });
  });
}

async function saveProject() {
  if (!S.current) return;
  try {
    await api('PATCH', '/api/conversations/' + S.current.id, { project: S.project });
    $('#saveState').textContent = '已保存';
    $('#saveState').classList.add('saved');
    setTimeout(() => {
      $('#saveState').textContent = '自动保存';
      $('#saveState').classList.remove('saved');
    }, 1600);
  } catch (e) { toast('保存失败：' + e.message); }
}

/* ---------------------------------------------------------- 设置 */
function openSettings(tab) {
  savedCfg = JSON.parse(JSON.stringify(S.config));
  settingsSaved = false;
  draftCfg = JSON.parse(JSON.stringify(S.config));
  editPid = draftCfg.activeProviderId;
  $('#modal').classList.add('show');
  $('#modalMask').classList.add('show');
  setTab(tab || 'model');
}

function closeSettings() {
  $('#modal').classList.remove('show');
  $('#modalMask').classList.remove('show');
  if (!settingsSaved && savedCfg) {
    S.config = savedCfg;
    applyAppearance();
    updateModelChip();
  }
}

function setTab(tab) {
  curTab = tab;
  $$('#tabs .tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  renderTab();
}

function providerOf(pid) {
  return (draftCfg.providers || []).find(p => p.id === pid);
}

function renderTab() {
  const body = $('#modalBody');
  const note = $('#modalNote'), saveBtn = $('#btnSaveSettings');
  if (note) {
    note.textContent = curTab === 'store'
      ? '工作区更改后需要重启软件生效'
      : '配置保存在本机 data/config.json';
  }
  if (saveBtn) saveBtn.classList.toggle('hidden', curTab === 'store');
  if (curTab === 'model') body.innerHTML = modelTabHtml();
  else if (curTab === 'gen') body.innerHTML = genTabHtml();
  else if (curTab === 'look') body.innerHTML = lookTabHtml();
  else if (curTab === 'store') body.innerHTML = storeTabHtml();
  else body.innerHTML = prefTabHtml();
  bindTab();
}

function modelTabHtml() {
  const list = (draftCfg.providers || []).map(p => {
    const ready = p.apiKey || p.kind === 'ollama' || /localhost|127\.0\.0\.1/.test(p.baseUrl || '');
    return '<button class="pv-item' + (p.id === editPid ? ' active' : '') + '" data-pv="' + p.id + '">' +
      '<span class="' + (ready ? 'ok' : 'no') + '"></span>' + esc(p.name) + '</button>';
  }).join('');
  const p = providerOf(editPid) || {};
  const models = (p.models || []).map(m => '<button class="chip" data-model="' + esc(m) + '">' + esc(m) + '</button>').join('');
  const kindOpts = [['openai', 'OpenAI 兼容'], ['anthropic', 'Anthropic'], ['ollama', 'Ollama 原生']]
    .map(([v, t]) => '<option value="' + v + '"' + (p.kind === v ? ' selected' : '') + '>' + t + '</option>').join('');

  return '<div class="pv-wrap"><div class="pv-list">' + list +
    '<button class="pv-add" id="pvAdd">＋ 自定义服务</button></div>' +
    '<div class="pv-form">' +
    '<div class="row"><label>服务商名称</label><input class="input" data-pf="name" value="' + esc(p.name || '') + '"></div>' +
    '<div class="grid2">' +
    '<div class="row"><label>协议</label><select class="select" data-pf="kind">' + kindOpts + '</select></div>' +
    '<div class="row"><label>模型名称</label><input class="input" data-pf="model" value="' + esc(p.model || '') + '" placeholder="deepseek-chat"></div>' +
    '</div>' +
    '<div class="row"><label>API 地址</label><input class="input" data-pf="baseUrl" value="' + esc(p.baseUrl || '') + '" placeholder="https://api.example.com/v1">' +
    '<div class="tip">填到 /v1 即可；本地 Ollama 用 http://localhost:11434，LM Studio 用 http://localhost:1234/v1</div></div>' +
    '<div class="row"><label>API Key</label><input class="input" type="password" data-pf="apiKey" value="' + esc(p.apiKey || '') + '" placeholder="sk-…（本地模型可留空）"></div>' +
    (models ? '<div class="chips">' + models + '</div>' : '') +
    '<div class="test-row"><button class="ghost" id="btnTest" style="border-color:var(--line)">测试连接</button>' +
    '<button class="ghost" id="btnUseProvider" style="border-color:var(--line)">' +
    (draftCfg.activeProviderId === editPid ? '当前使用中' : '设为当前模型') + '</button>' +
    '<span class="test-result" id="testResult"></span></div>' +
    '<div class="tip" style="margin-top:16px;border-top:1px solid var(--line-soft);padding-top:12px;line-height:1.75">' +
    '密钥只写入本机 <code style="font-family:var(--mono);font-size:10.5px">data/config.json</code>，不会上传到任何第三方。' +
    '用本地模型时：先启动 Ollama（默认 11434）或 LM Studio（默认 1234），再用 <code style="font-family:var(--mono);font-size:10.5px">ollama pull 模型名</code> 拉取模型。' +
    '</div>' +
    '</div></div>';
}

function genTabHtml() {
  const p = draftCfg.params || {};
  return '<div style="max-width:460px">' +
    '<div class="row"><label>Temperature · 变化程度</label>' +
    '<div class="slider-row"><input type="range" min="0" max="1.5" step="0.05" id="rTemp" value="' + (p.temperature ?? 0.85) + '">' +
    '<span class="val" id="vTemp">' + (p.temperature ?? 0.85) + '</span></div>' +
    '<div class="tip">0.6 偏稳（改稿 / 学术），0.85 均衡（长篇），1.1 以上更发散（脑暴）。</div></div>' +
    '<div class="row"><label>Top P</label>' +
    '<div class="slider-row"><input type="range" min="0.1" max="1" step="0.05" id="rTopP" value="' + (p.topP ?? 0.95) + '">' +
    '<span class="val" id="vTopP">' + (p.topP ?? 0.95) + '</span></div></div>' +
    '<div class="row"><label>单次最大输出 Token</label>' +
    '<input class="input" type="number" id="iMax" value="' + (p.maxTokens ?? 8192) + '" min="0" step="512">' +
    '<div class="tip">本地模型建议 8192 以上；填 0 表示不限制（仅 Ollama 生效）。写整章约需 3000-6000。</div></div>' +
    '<div class="row"><label>上下文窗口 num_ctx（Ollama）</label>' +
    '<input class="input" type="number" id="iCtx" value="' + (p.ctx ?? 8192) + '" min="0" step="1024">' +
    '<div class="tip">Ollama 默认只有 4096，长篇的设定与历史会被悄悄截掉，模型就会答到一半停住。建议 8192-32768，但不要超过显卡能承受的范围。</div></div>' +
    '<div class="row"><label>上下文预算（字符）</label>' +
    '<input class="input" type="number" id="iBudget" value="' + (p.contextBudget ?? 16000) + '" min="2000" step="1000">' +
    '<div class="tip">未压缩的对话超过这个长度时，会自动把早期消息合并成「前情提要」。写长篇建议 12000-24000。</div></div>' +
    '</div>';
}

function lookTabHtml() {
  const a = draftCfg.appearance || {};
  const cur = a.theme || 'paper';
  const th = themeById(cur);

  const cards = THEMES.map(t => {
    const p = t.vars['--paper'], ac = t.vars['--accent'], ln = t.vars['--line'];
    return '<button class="theme-card' + (t.id === cur ? ' active' : '') + '" data-theme="' + t.id + '">' +
      '<span class="prev" style="background:' + t.bg + '">' +
      '<b style="background:' + p + ';border-color:' + ln + ';border-left-color:' + ac + '"></b></span>' +
      '<span class="tname"><span>' + t.name + '</span><span>' + t.tag + '</span></span></button>';
  }).join('');

  const accent = String(a.accent || th.vars['--accent']).toLowerCase();
  const sw = ACCENT_PRESETS.map(c =>
    '<button class="swatch' + (c.toLowerCase() === accent ? ' active' : '') +
    '" data-accent="' + c + '" style="background:' + c + '"></button>').join('');

  const thumbs = (S.bgs || []).map(b =>
    '<div class="bg-thumb' + (a.backgroundId === b.id ? ' active' : '') + '" data-bg="' + b.id + '">' +
    '<img src="' + b.url + '" alt=""><button class="del" data-del="' + b.id + '">×</button></div>').join('');

  const radius = a.radius != null ? a.radius : parseInt(th.vars['--radius'], 10);
  const fsize = a.fontSize || 17;
  const pct = Math.round((a.panelOpacity == null ? 1 : a.panelOpacity) * 100);
  const isImg = !!a.backgroundId;

  return '<div class="sec-title">主题</div><div class="theme-grid">' + cards + '</div>' +
    '<div class="sec-title">强调色</div><div class="swatches">' + sw +
    '<input type="color" id="accentPick" value="' + accent + '" title="自定义颜色">' +
    '<button class="ghost" id="accentReset" style="border-color:var(--line);font-size:11px;padding:4px 9px">跟随主题</button></div>' +
    '<div class="sec-title">排版</div>' +
    '<div class="slider-row"><label>圆角</label><input type="range" min="0" max="20" step="1" id="rRadius" value="' + radius + '"><span class="val" id="vRadius">' + radius + 'px</span></div>' +
    '<div class="slider-row"><label>正文字号</label><input type="range" min="14" max="22" step="1" id="rFont" value="' + fsize + '"><span class="val" id="vFont">' + fsize + 'px</span></div>' +
    '<div class="slider-row"><label>面板浓度</label><input type="range" min="50" max="120" step="2" id="rPanel" value="' + pct + '"><span class="val" id="vPanel">' + pct + '%</span></div>' +
    '<div class="sec-title">背景图</div><div class="bg-grid">' +
    '<button class="upload-tile" id="tileUpload"><svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M10 14V5m0 0L6.5 8.5M10 5l3.5 3.5"/><path d="M3.5 14.5v1a1.5 1.5 0 0 0 1.5 1.5h10a1.5 1.5 0 0 0 1.5-1.5v-1"/></svg><span>导入图片</span></button>' +
    thumbs + '</div>' +
    '<div class="tip" style="margin-top:8px">支持 JPG / PNG / WEBP / GIF，单张 ≤ 16MB。不选图片时使用主题自带底色。</div>' +
    (isImg ? '<div class="sec-title">图片调节</div>' +
      '<div class="slider-row"><label>浓度</label><input type="range" min="0.05" max="1" step="0.05" id="rInt" value="' + (a.intensity ?? 0.55) + '"><span class="val" id="vInt">' + Math.round((a.intensity ?? 0.55) * 100) + '%</span></div>' +
      '<div class="slider-row"><label>模糊</label><input type="range" min="0" max="20" step="1" id="rBlur" value="' + (a.blur || 0) + '"><span class="val" id="vBlur">' + (a.blur || 0) + 'px</span></div>' +
      '<div class="slider-row"><label>遮罩</label><input type="range" min="0" max="0.85" step="0.01" id="rDim" value="' + (a.dim ?? 0.12) + '"><span class="val" id="vDim">' + Math.round((a.dim ?? 0.12) * 100) + '%</span></div>' : '') +
    (hasBridge() ? '<div class="row" style="margin-top:16px;border-top:1px solid var(--line-soft);padding-top:14px">' +
      '<label>数据位置</label><button class="ghost" id="btnDataDir" style="border-color:var(--line)">打开数据文件夹</button>' +
      '<div class="tip">作品、设定与背景图都保存在这里，复制整个 data 文件夹即可备份。</div></div>' : '');
}

/* ---------------------------------------------------------- 素材（参考资料） */
function renderMaterials() {
  const box = $('#materials');
  if (!box) return;
  const list = (S.current && S.current.materials) || [];
  if (!list.length) { box.classList.add('hidden'); box.innerHTML = ''; return; }
  box.classList.remove('hidden');
  box.innerHTML = list.map((m, i) =>
    '<span class="mat-chip" title="' + esc(m.name || '') + '">' +
    '<b>' + esc(m.name || '材料') + '</b><i>' + fmtK(m.chars || 0) + ' 字</i>' +
    '<button data-mat="' + i + '" title="移除">×</button></span>').join('');
  box.querySelectorAll('[data-mat]').forEach(b => {
    b.onclick = async () => {
      const i = +b.dataset.mat;
      S.current.materials.splice(i, 1);
      try {
        await api('PATCH', '/api/conversations/' + S.current.id, { materials: S.current.materials });
      } catch (e) { toast(e.message); }
      renderMaterials();
      renderInspector();
    };
  });
}

async function attachFile() {
  if (hasBridge()) {
    try {
      const r = await window.pywebview.api.pick_doc_file();
      if (!r || !r.data) return;
      await doAttach(r.name, r.data);
    } catch (e) { toast('打开文件失败：' + e.message); }
  } else {
    $('#fileDoc').click();
  }
}

async function doAttach(name, data) {
  toast('正在读取 ' + name + '…', 8000);
  try {
    const r = await api('POST', '/api/files/extract', { filename: name, data });
    if (!S.current) {
      S.current = await api('POST', '/api/conversations', { skillId: S.skillId });
      S.project = S.current.project || {};
    }
    S.current.materials = S.current.materials || [];
    S.current.materials.push({
      id: Date.now().toString(36),
      name: r.name, chars: r.chars, text: r.text,
    });
    await api('PATCH', '/api/conversations/' + S.current.id, { materials: S.current.materials });
    renderMaterials();
    renderInspector();
    toast('已加入素材：' + r.name + '（' + fmtK(r.chars) + ' 字）' + (r.truncated ? '，超出部分已截断' : ''), 3600);
  } catch (e) {
    toast(e.message || '读取失败', 4200);
  }
}

/* ---------------------------------------------------------- 指令（输入 / 唤起） */
const COMMANDS = [
  { key: '/压缩', alias: '/compact', desc: '把早期对话压成前情提要', run: () => compactContext() },
  { key: '/新建', alias: '/new', desc: '新建一篇创作', run: () => newConv() },
  { key: '/导出', alias: '/export', desc: '导出当前作品为 Markdown', run: () => exportMd() },
  { key: '/技能', alias: '/skill', desc: '打开技能列表', run: () => setView('skills') },
  { key: '/主题', alias: '/theme', desc: '打开外观与主题', run: () => openSettings('look') },
  { key: '/帮助', alias: '/help', desc: '显示所有指令', run: () => { showCommands(true); return 'keep'; } },
];

let cmdIndex = 0;
let cmdList = [];

function matchCommands(v) {
  const q = (v || '').trim().toLowerCase();
  if (!q.startsWith('/')) return [];
  return COMMANDS.filter(c => c.key.startsWith(q) || c.alias.startsWith(q));
}

function showCommands(forceAll) {
  const ta = $('#input');
  const v = forceAll ? '/' : ta.value;
  cmdList = matchCommands(v);
  cmdIndex = 0;
  const pop = $('#cmdPop');
  if (!pop) return;
  if (!cmdList.length) { pop.classList.add('hidden'); pop.innerHTML = ''; return; }
  pop.innerHTML = cmdList.map((c, i) =>
    '<div class="cmd-item' + (i === 0 ? ' on' : '') + '" data-cmd="' + i + '">' +
    '<b>' + c.key + '</b><span>' + c.desc + '</span><i>' + c.alias + '</i></div>').join('');
  pop.classList.remove('hidden');
  pop.querySelectorAll('[data-cmd]').forEach(el => {
    el.onmousedown = (e) => { e.preventDefault(); runCommand(cmdList[+el.dataset.cmd]); };
  });
}

function hideCommands() {
  const pop = $('#cmdPop');
  if (pop) { pop.classList.add('hidden'); pop.innerHTML = ''; }
  cmdList = [];
}

function runCommand(c) {
  const ta = $('#input');
  if (c.run() !== 'keep') { ta.value = ''; autosize(); }
  hideCommands();
  ta.focus();
}

function moveCmd(delta) {
  if (!cmdList.length) return;
  cmdIndex = (cmdIndex + delta + cmdList.length) % cmdList.length;
  const pop = $('#cmdPop');
  pop.querySelectorAll('.cmd-item').forEach((el, i) => el.classList.toggle('on', i === cmdIndex));
}

function fmtK(n) {
  return n >= 10000 ? (n / 1000).toFixed(1) + 'k' : String(n);
}

/* ---------------------------------------------------------- 导入技能 */
async function importSkill() {
  if (hasBridge()) {
    try {
      const r = await window.pywebview.api.pick_skill_file();
      if (!r || !r.data) return;
      await doImport(r.name, r.data);
    } catch (e) { toast('打开文件失败：' + e.message); }
  } else {
    $('#fileSkill').click();
  }
}

async function doImport(name, data) {
  toast('正在导入…');
  try {
    const r = await api('POST', '/api/skills/import', { filename: name, data });
    if (r.imported && r.imported.length) {
      S.skills = r.skills;
      if (S.view === 'skills') renderSkillList();
      const names = r.imported.map(x => x.name).join('、');
      toast('已导入：' + names, 3600);
    } else {
      const why = (r.skipped && r.skipped[0] && r.skipped[0].reason) || '没有找到可用的技能';
      toast('没导入成功：' + why, 4000);
    }
  } catch (e) { toast('导入失败：' + e.message); }
}

/* ---------------------------------------------------------- 压缩上下文 */
async function compactContext() {
  if (!S.current) { toast('先打开或新建一篇作品'); return; }
  const msgs = S.current.messages || [];
  if (msgs.length < 8) { toast('消息还少，暂时不需要压缩'); return; }
  toast('正在压缩上下文…', 8000);
  try {
    const r = await api('POST', '/api/conversations/' + S.current.id + '/compress');
    if (r.skipped) { toast(r.message || '不需要压缩'); return; }
    S.current.summary = r.result.summary;
    S.current.summaryCount = r.result.merged;
    renderThread();
    renderInspector();
    toast('已压缩：' + fmtK(r.result.before) + ' → ' + fmtK(r.result.after) + ' 字', 4000);
  } catch (e) { toast('压缩失败：' + e.message, 4200); }
}

function hasBridge() {
  return !!(window.pywebview && window.pywebview.api);
}

function fmtBytes(n) {
  n = n || 0;
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  if (n < 1073741824) return (n / 1048576).toFixed(1) + ' MB';
  return (n / 1073741824).toFixed(2) + ' GB';
}

function storeTabHtml() {
  setTimeout(loadStorage, 0);
  return '<div id="storeBox"><div class="tip" style="padding:24px 0">读取中…</div></div>';
}

async function loadStorage() {
  const box = $('#storeBox');
  if (!box) return;
  let d;
  try {
    d = await api('GET', '/api/storage');
  } catch (e) {
    box.innerHTML = '<div class="store-warn">读取失败：' + esc(e.message) + '</div>';
    return;
  }
  const srcLabel = d.source === 'custom'
    ? '自定义位置'
    : (d.source === 'appdir' ? '默认位置（软件所在目录）' : '系统目录（软件目录不可写）');
  const rows = [
    ['书稿', d.sizes.books], ['对话记录', d.sizes.chats],
    ['自定义背景', d.sizes.backgrounds], ['导入的技能', d.sizes.skills],
  ];
  let html = '<div class="field"><label>工作区位置</label>' +
    '<div class="path-row">' +
    '<input class="input" id="storePath" readonly value="' + esc(d.dataDir) + '">' +
    '<button class="mini" id="storeOpen">打开</button>' +
    '<button class="mini" id="storeCopy">复制</button>' +
    '</div>' +
    '<div class="tip">书稿、设定库、对话、导入的技能和背景图都在这个文件夹里。' +
    '换电脑时整个拷走就能继续写。</div></div>';
  html += '<div class="store-badge' + (d.source === 'custom' ? ' custom' : '') + '">' +
    esc(srcLabel) + '</div>';
  if (d.warning) html += '<div class="store-warn">' + esc(d.warning) + '</div>';
  html += '<div class="store-sizes">' +
    rows.map(([k, v]) => '<div class="stat-row"><span>' + k + '</span><span>' +
      fmtBytes(v) + '</span></div>').join('') +
    '<div class="stat-row"><span>合计</span><span>' + fmtBytes(d.total) + '</span></div></div>';
  html += '<div class="store-acts">' +
    '<button class="ghost" id="storeMove">更改位置…</button>' +
    (d.isDefault ? '' : '<button class="ghost" id="storeReset">恢复默认</button>') +
    '</div>';
  html += '<div class="tip" style="margin-top:12px">更改位置会把现有数据复制到新文件夹，' +
    '原目录不会删除。复制完成后需要重启软件才生效。</div>';
  box.innerHTML = html;

  $('#storeOpen').onclick = async () => {
    try { await api('POST', '/api/storage/reveal', { path: d.dataDir }); }
    catch (e) { toast(e.message); }
  };
  $('#storeCopy').onclick = () => copyText(d.dataDir);
  $('#storeMove').onclick = () => changeStorage();
  const rs = $('#storeReset');
  if (rs) rs.onclick = async () => {
    if (!confirm('恢复默认位置？\n\n下次启动会用软件目录下的 data 文件夹。当前目录里的文件不会删除。')) return;
    try {
      const r = await api('POST', '/api/storage/reset', {});
      showStorageDone(r.dataDir, false);
    } catch (e) { toast(e.message); }
  };
}

async function changeStorage() {
  let path = '';
  if (hasBridge() && window.pywebview && window.pywebview.api &&
      window.pywebview.api.pick_folder) {
    const r = await window.pywebview.api.pick_folder();
    if (!r || !r.ok) { if (r && r.message && r.message !== '已取消') toast(r.message); return; }
    path = r.path;
  } else {
    path = window.prompt('新工作区文件夹（必须是空文件夹，例如 D:////我的小说）', '');
    if (!path) return;
  }
  if (!confirm('把当前工作区复制到：\n' + path + '\n\n原目录不会删除。复制完成后需要重启软件。')) return;
  const box = $('#storeBox');
  if (box) box.innerHTML = '<div class="tip" style="padding:24px 0">正在复制，别关窗口…</div>';
  try {
    const d = await api('POST', '/api/storage/move', { path });
    showStorageDone(d.dataDir, true);
  } catch (e) {
    toast(e.message);
    loadStorage();
  }
}

function showStorageDone(dir, moved) {
  const box = $('#storeBox');
  if (!box) return;
  box.innerHTML = '<div class="store-done">' +
    '<div class="sd-h">' + (moved ? '已复制到新位置' : '已恢复默认设置') + '</div>' +
    '<div class="sd-p">' + esc(dir) + '</div>' +
    '<div class="tip">重启软件后生效。' +
    (moved ? '原目录里的文件还在，确认新位置一切正常后可以手动删掉。' : '') +
    '</div>' +
    '<button class="primary" id="storeRestart">立即重启</button></div>';
  $('#storeRestart').onclick = async () => {
    if (hasBridge() && window.pywebview && window.pywebview.api &&
        window.pywebview.api.restart_app) {
      await window.pywebview.api.restart_app();
    } else {
      toast('请手动关闭软件再重新打开', 4000);
    }
  };
}

function prefTabHtml() {
  const p = draftCfg.prefs || {};
  const langs = ['中文', '繁體中文', 'English', '中英混排'];
  const opts = langs.map(l => '<option' + (p.language === l ? ' selected' : '') + '>' + l + '</option>').join('');
  const presets = ['不用成语', '不写排比句', '不写心理描写', '每段不超过三句',
                   '用第二人称', '只写动作和对话', '不出现现代词汇'];
  return '<div style="max-width:520px">' +
    '<div class="row"><label>规则词</label>' +
    '<textarea class="textarea" id="pRules" rows="6" placeholder="一行一条，每次请求都会带上。\n例如：\n不用成语\n不写心理描写\n每段不超过三句">' +
    esc(p.rules || '') + '</textarea>' +
    '<div class="chips">' + presets.map(x =>
      '<button class="chip" data-rule="' + esc(x) + '">' + esc(x) + '</button>').join('') + '</div>' +
    '<div class="tip">优先级最高：与技能、写作偏好冲突时，以规则词为准。点上面的词可以快速追加。</div></div>' +
    '<div class="row"><label>输出语言</label><select class="select" id="pLang">' + opts + '</select></div>' +
    '<div class="row"><label>语气</label><input class="input" id="pTone" value="' + esc(p.tone || '') + '" placeholder="冷峻克制 / 轻快幽默 / 平实口语"></div>' +
    '<div class="row"><label>默认篇幅</label><input class="input" id="pLen" value="' + esc(p.length || '') + '" placeholder="每章 3000 字 / 短文 1200 字"></div>' +
    '</div>';
}

function bindTab() {
  const body = $('#modalBody');
  if (curTab === 'store') return;

  if (curTab === 'model') {
    body.querySelectorAll('[data-pv]').forEach(b => {
      b.onclick = () => { editPid = b.dataset.pv; renderTab(); };
    });
    body.querySelectorAll('[data-pf]').forEach(inp => {
      inp.addEventListener('input', () => {
        const p = providerOf(editPid);
        if (p) p[inp.dataset.pf] = inp.value;
      });
      inp.addEventListener('change', () => {
        const p = providerOf(editPid);
        if (p) p[inp.dataset.pf] = inp.value;
      });
    });
    body.querySelectorAll('[data-model]').forEach(b => {
      b.onclick = () => {
        const p = providerOf(editPid);
        if (p) { p.model = b.dataset.model; renderTab(); }
      };
    });
    const add = $('#pvAdd');
    if (add) add.onclick = () => {
      const id = 'custom-' + Date.now().toString(36);
      draftCfg.providers.push({
        id, name: '自定义服务', kind: 'openai',
        baseUrl: 'http://localhost:8000/v1', apiKey: '', model: '', models: [],
      });
      editPid = id;
      renderTab();
    };
    const use = $('#btnUseProvider');
    if (use) use.onclick = () => {
      draftCfg.activeProviderId = editPid;
      renderTab();
      toast('保存后生效');
    };
    const test = $('#btnTest');
    if (test) test.onclick = async () => {
      const p = providerOf(editPid);
      const res = $('#testResult');
      res.className = 'test-result';
      res.textContent = '连接中…';
      test.disabled = true;
      try {
        const d = await api('POST', '/api/test', {
          providerId: editPid, baseUrl: p.baseUrl, apiKey: p.apiKey, model: p.model,
        });
        res.className = 'test-result ' + (d.ok ? 'ok' : 'bad');
        res.textContent = d.message;
      } catch (e) {
        res.className = 'test-result bad';
        res.textContent = e.message;
      } finally { test.disabled = false; }
    };
  }

  if (curTab === 'gen') {
    const bind = (rid, vid, key, fmt) => {
      const r = $('#' + rid), v = $('#' + vid);
      if (!r) return;
      r.oninput = () => {
        draftCfg.params[key] = parseFloat(r.value);
        v.textContent = fmt ? fmt(r.value) : r.value;
      };
    };
    bind('rTemp', 'vTemp', 'temperature');
    bind('rTopP', 'vTopP', 'topP');
    const mx = $('#iMax');
    if (mx) mx.oninput = () => { draftCfg.params.maxTokens = parseInt(mx.value || '0', 10); };
    const cx = $('#iCtx');
    if (cx) cx.oninput = () => { draftCfg.params.ctx = parseInt(cx.value || '0', 10); };
    const bg = $('#iBudget');
    if (bg) bg.oninput = () => { draftCfg.params.contextBudget = parseInt(bg.value || '16000', 10); };
  }

  if (curTab === 'look') {
    const live = () => {
      S.config = JSON.parse(JSON.stringify(draftCfg));
      applyAppearance();
    };
    const refresh = () => { live(); renderTab(); };

    body.querySelectorAll('[data-theme]').forEach(el => {
      el.onclick = () => {
        draftCfg.appearance.theme = el.dataset.theme;
        draftCfg.appearance.accent = null;
        draftCfg.appearance.radius = null;
        refresh();
      };
    });

    body.querySelectorAll('[data-accent]').forEach(el => {
      el.onclick = () => { draftCfg.appearance.accent = el.dataset.accent; refresh(); };
    });
    const pick = $('#accentPick');
    if (pick) pick.oninput = () => { draftCfg.appearance.accent = pick.value; live(); };
    const reset = $('#accentReset');
    if (reset) reset.onclick = () => { draftCfg.appearance.accent = null; refresh(); };

    const bindS = (rid, vid, key, fmt, tr) => {
      const r = $('#' + rid), v = $('#' + vid);
      if (!r) return;
      r.oninput = () => {
        const raw = parseFloat(r.value);
        draftCfg.appearance[key] = tr ? tr(raw) : raw;
        v.textContent = fmt(raw);
        live();
      };
    };
    bindS('rRadius', 'vRadius', 'radius', v => v + 'px');
    bindS('rFont', 'vFont', 'fontSize', v => v + 'px');
    bindS('rPanel', 'vPanel', 'panelOpacity', v => v + '%', v => v / 100);
    bindS('rInt', 'vInt', 'intensity', v => Math.round(v * 100) + '%');
    bindS('rBlur', 'vBlur', 'blur', v => v + 'px');
    bindS('rDim', 'vDim', 'dim', v => Math.round(v * 100) + '%');

    body.querySelectorAll('[data-bg]').forEach(el => {
      el.onclick = (e) => {
        if (e.target.dataset.del) return;
        draftCfg.appearance.backgroundId = el.dataset.bg;
        if (draftCfg.appearance.intensity == null) draftCfg.appearance.intensity = 0.6;
        refresh();
      };
    });
    body.querySelectorAll('[data-del]').forEach(b => {
      b.onclick = async (e) => {
        e.stopPropagation();
        const id = b.dataset.del;
        await api('DELETE', '/api/backgrounds/' + id).catch(() => { });
        S.bgs = S.bgs.filter(x => x.id !== id);
        if (draftCfg.appearance.backgroundId === id) draftCfg.appearance.backgroundId = null;
        refresh();
      };
    });
    const up = $('#tileUpload');
    if (up) up.onclick = () => $('#fileBg').click();

    const dd = $('#btnDataDir');
    if (dd) dd.onclick = () => { try { window.pywebview.api.open_data_dir(); } catch (e) { } };
  }

  if (curTab === 'pref') {
    const g = (id) => $('#' + id);
    if (g('pLang')) g('pLang').onchange = e => draftCfg.prefs.language = e.target.value;
    if (g('pTone')) g('pTone').oninput = e => draftCfg.prefs.tone = e.target.value;
    if (g('pLen')) g('pLen').oninput = e => draftCfg.prefs.length = e.target.value;
    if (g('pRules')) g('pRules').oninput = e => draftCfg.prefs.rules = e.target.value;
    body.querySelectorAll('[data-rule]').forEach(b => {
      b.onclick = () => {
        const v = draftCfg.prefs.rules || '';
        const line = b.dataset.rule;
        if (v.split('\n').map(x => x.trim()).includes(line)) return;
        draftCfg.prefs.rules = (v.trim() ? v.replace(/\s+$/, '') + '\n' : '') + line;
        renderTab();
      };
    });
  }
}

async function saveSettings() {
  try {
    const r = await api('POST', '/api/config', draftCfg);
    S.config = r.config;
    settingsSaved = true;
    applyAppearance();
    updateModelChip();
    closeSettings();
    toast('设置已保存');
  } catch (e) { toast('保存失败：' + e.message); }
}

/* ---------------------------------------------------------- 导出 */
async function exportMd() {
  if (!S.current || !S.current.messages.length) { toast('还没有内容可导出'); return; }
  try {
    const d = await api('POST', '/api/export', { id: S.current.id });
    // 桌面版：走系统原生「另存为」对话框
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_markdown) {
      const r = await window.pywebview.api.save_markdown(d.filename, d.content);
      if (r && r.ok) toast(r.message);
      else if (r && r.message && r.message !== '已取消') toast(r.message);
      return;
    }
    // 浏览器回退：直接下载
    const blob = new Blob([d.content], { type: 'text/markdown;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = d.filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    toast('已导出 ' + d.filename);
  } catch (e) { toast(e.message); }
}

/* ---------------------------------------------------------- 事件 */
function bindEvents() {
  $('#btnNew').onclick = () => {
    if (S.view === 'book') {
      if (BK.book) return newChapter();
      return newBookFlow();
    }
    return newConv();
  };
  $('#btnSettings').onclick = () => openSettings('model');
  $('#btnModel').onclick = () => openSettings('model');
  $('#btnBg').onclick = () => openSettings('look');
  const imp = $('#btnImportSkill');
  if (imp) imp.onclick = importSkill;
  const cmp = $('#btnCompact');
  if (cmp) cmp.onclick = compactContext;
  const at = $('#btnAttach');
  if (at) at.onclick = attachFile;
  const fd = $('#fileDoc');
  if (fd) fd.onchange = () => {
    const f = fd.files && fd.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => doAttach(f.name, String(r.result).split(',')[1] || '');
    r.readAsDataURL(f);
    fd.value = '';
  };
  const fs = $('#fileSkill');
  if (fs) fs.onchange = () => {
    const f = fs.files && fs.files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => doImport(f.name, String(r.result).split(',')[1] || '');
    r.readAsDataURL(f);
    fs.value = '';
  };
  const look = $('#btnLook');
  if (look) look.onclick = () => openSettings('look');
  $('#btnProject').onclick = async () => {
    if (!S.current) {
      try {
        S.current = await api('POST', '/api/conversations', { skillId: S.skillId });
        S.project = S.current.project || {};
        renderPanel();
        renderInspector();
      } catch (e) { return; }
    }
    S.project = S.current.project || S.project || {};
    renderProject();
    $('#drawer').classList.add('open');
    $('#drawerMask').classList.add('show');
  };
  $('#btnDrawerClose').onclick = () => {
    $('#drawer').classList.remove('open');
    $('#drawerMask').classList.remove('show');
    if (S.view === 'book') return;
    clearTimeout(S.projectTimer);
    saveProject();
  };
  $('#drawerMask').onclick = () => $('#btnDrawerClose').click();
  $('#btnClearProject').onclick = () => {
    if (!confirm('清空本作品的创作档案？')) return;
    S.project = {};
    renderProject();
    saveProject();
  };
  $('#btnExport').onclick = exportMd;

  $('#skillPick').onclick = openSkillPop;
  $('#skillMask').onclick = closeSkillPop;
  $('#skillPopBody').addEventListener('click', e => {
    const w = e.target.closest('[data-wf]');
    if (w) {
      closeSkillPop();
      if (!w.dataset.wf) return exitWorkflow();
      return startWorkflow(w.dataset.wf);
    }
    const b = e.target.closest('[data-skill]');
    if (b) pickSkill(b.dataset.skill);
  });

  $('#btnMenu').onclick = () => $('#panel').classList.toggle('open');
  $$('.rail-btn[data-view]').forEach(b => b.onclick = () => setView(b.dataset.view));
  const ci = $('#btnCorpusImport'); if (ci) ci.onclick = corpusImport;
  const cr = $('#btnCorpusReport'); if (cr) cr.onclick = corpusReport;

  $('#btnSend').onclick = () => send(false);
  $('#btnStop').onclick = () => { if (S.ctrl) S.ctrl.abort(); };

  const ta = $('#input');
  ta.addEventListener('input', autosize);
  ta.addEventListener('keydown', e => {
    if (cmdList.length) {
      if (e.key === 'ArrowDown') { e.preventDefault(); moveCmd(1); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); moveCmd(-1); return; }
      if (e.key === 'Escape') { e.preventDefault(); hideCommands(); return; }
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        runCommand(cmdList[cmdIndex] || cmdList[0]);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send(false);
    }
  });

  ta.addEventListener('input', () => {
    if (ta.value.startsWith('/') && !ta.value.includes('\n')) showCommands(false);
    else hideCommands();
  });

  $$('#tabs .tab').forEach(b => b.onclick = () => setTab(b.dataset.tab));
  $('#btnModalClose').onclick = closeSettings;
  $('#modalMask').onclick = closeSettings;
  $('#btnSaveSettings').onclick = saveSettings;

  $('#fileBg').addEventListener('change', e => {
    const f = e.target.files && e.target.files[0];
    uploadBg(f);
    e.target.value = '';
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeSettings(); closeSkillPop();
      $('#drawer').classList.remove('open');
      $('#drawerMask').classList.remove('show');
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault(); openSkillPop();
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
      e.preventDefault(); newConv();
    }
  });

  window.addEventListener('beforeunload', () => {
    if (S.projectTimer) { clearTimeout(S.projectTimer); }
    if (BK && BK.dirty && BK.chapter && S.bookId) {
      try {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', '/api/books/' + S.bookId + '/chapters/' + BK.chapter.id, false);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify({ text: $('#chText').value, title: $('#chTitle').value }));
      } catch (_) { }
    }
  });

  bindBookEvents();
}

/* ============================================================
   书稿视图
   ============================================================ */
const BK = {
  list: [], book: null, chapter: null, tab: 'bible',
  dirty: false, timer: null, hits: [], rhythm: null, graph: null,
};

function fmtW(n) {
  n = n || 0;
  return n >= 10000 ? (n / 10000).toFixed(1) + ' 万' : String(n);
}

function countChars(t) {
  const han = (String(t).match(/[\u4e00-\u9fff]/g) || []).length;
  const en = (String(t).match(/[A-Za-z]+/g) || []).length;
  return han + en;
}

function updateWords() {
  const n = countChars($('#chText').value);
  $('#chWords').textContent = fmtW(n) + ' 字';
}

/* ---------------------------------------------- 书稿列表 / 打开 */
async function loadBooks() {
  try {
    const d = await api('GET', '/api/books');
    BK.list = d.books || [];
  } catch (e) { BK.list = []; }
}

async function openBook(bid) {
  try {
    const d = await api('GET', '/api/books/' + bid);
    BK.book = d;
    BK.chapter = null;
    S.bookId = bid;
    S.chapterId = null;
    BK.hits = [];
    setBookHeader(d.book.title || '', false);
    renderBookMeta();
    renderBookPanel();
    renderBookInspector();
    const first = (d.chapters || [])[0];
    if (first) openChapter(first.id);
    else showChapterEmpty();
    if (BK.pendingQuery) {
      const pq = BK.pendingQuery;
      BK.pendingQuery = '';
      BK.tab = 'search';
      renderBookInspector();
      doSearch(pq);
    }
    $('#panel').classList.remove('open');
  } catch (e) { toast('打开失败：' + e.message); }
}

async function refreshBook() {
  if (!S.bookId) return;
  try {
    const d = await api('GET', '/api/books/' + S.bookId);
    BK.book = d;
    renderBookMeta();
    renderBookPanel();
    renderBookInspector();
  } catch (e) { /* 静默 */ }
}

function renderBookMeta() {
  const st = (BK.book && BK.book.stats) || {};
  const drift = (BK.book && BK.book.drift) || [];
  let s = (st.chapters || 0) + ' 章 · ' + fmtW(st.words || 0) + ' 字';
  if (st.openForeshadow) s += ' · 伏笔未收 ' + st.openForeshadow;
  if (drift.length) s += ' · ' + drift.length + ' 章提纲待同步';
  $('#bookMeta').textContent = s;
}

function showChapterEmpty() {
  $('#chEmpty').classList.remove('hidden');
  $('#chBody').classList.add('hidden');
}

function setBookHeader(title, isList) {
  const bt = $('#bookTitle');
  if (bt) {
    bt.value = title || '';
    bt.placeholder = isList ? '全部书稿' : '未命名书稿';
    bt.readOnly = !!isList;
  }
  const vb = $('#viewBook');
  if (vb) vb.classList.toggle('no-book', !!isList);
  const sub = $('#chEmpty .empty-sub');
  if (sub) sub.textContent = isList ? '从左边选一本书' : '左边选一章，或者新建一章';
}

/* ---------------------------------------------- 左栏：书列表 / 卷章树 */
function renderBookPanel() {
  const body = $('#panelBody');
  if (!body) return;
  if (!BK.book) {
    let h = BK.list.length
      ? BK.list.map(b =>
        '<div class="book-card' + (b.id === S.bookId ? ' active' : '') + '" data-bid="' + b.id + '">' +
        '<div class="bc-t">' + esc(b.title) + '</div>' +
        '<div class="bc-m">' + b.chapters + ' 章 · ' + fmtW(b.words) + ' 字</div>' +
        '<button class="bc-del" data-bdel="' + b.id + '" title="删除这本书">×</button></div>'
      ).join('')
      : '<div class="panel-empty">还没有书稿。<br>新建一本，或者把整本 txt / docx 拖进来。</div>';
    h += '<div class="book-acts">' +
      '<button class="ghost" id="bkNewBlank">＋ 新建</button>' +
      '<button class="ghost" id="bkImport">导入整本</button></div>';
    body.innerHTML = h;
    body.querySelectorAll('[data-bid]').forEach(el => {
      el.onclick = () => openBook(el.dataset.bid);
    });
    body.querySelectorAll('[data-bdel]').forEach(el => {
      el.onclick = e => { e.stopPropagation(); deleteBook(el.dataset.bdel); };
    });
    const nb = $('#bkNewBlank'), bi = $('#bkImport');
    if (nb) nb.onclick = newBookFlow;
    if (bi) bi.onclick = pickBookFile;
    return;
  }
  const b = BK.book.book;
  const chs = BK.book.chapters || [];
  let html = '<div class="back-books" id="backBooks">← 全部书稿</div>';
  (b.volumes || []).forEach(v => {
    const list = chs.filter(c => c.volumeId === v.id);
    html += '<div class="vol" data-vid="' + v.id + '">' +
      '<div class="vol-head">' +
      '<svg class="vol-caret" viewBox="0 0 12 12" width="9" height="9"><path d="M2.5 4 6 7.5 9.5 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>' +
      '<span class="t">' + esc(v.title) + '</span><span class="cnt">' + list.length + '</span></div>' +
      '<div class="vol-chs">' +
      (list.length ? list.map(chItemHtml).join('')
        : '<div class="bible-empty" style="padding:2px 10px 8px">空卷</div>') +
      '</div></div>';
  });
  html += '<div class="vol-add" id="volAdd">+ 新建卷</div>';
  html += '<div class="book-danger" id="delBook">删除本书</div>';
  body.innerHTML = html;
  body.querySelectorAll('.vol-head').forEach(h => {
    h.onclick = () => h.parentElement.classList.toggle('closed');
  });
  body.querySelectorAll('.ch-item').forEach(el => {
    el.onclick = () => openChapter(el.dataset.cid);
    bindChapterDrag(el);
  });
  body.querySelectorAll('[data-del]').forEach(el => {
    el.onclick = e => { e.stopPropagation(); deleteChapter(el.dataset.del); };
  });
  const va = $('#volAdd');
  if (va) va.onclick = newVolume;
  const db = $('#delBook');
  if (db) db.onclick = () => deleteBook(S.bookId);
  const bb = $('#backBooks');
  if (bb) bb.onclick = backToBooks;
}

async function backToBooks() {
  if (BK.dirty) await saveChapter();
  BK.book = null;
  BK.chapter = null;
  S.bookId = null;
  S.chapterId = null;
  showChapterEmpty();
  setBookHeader('', true);
  $('#bookMeta').textContent = '';
  await loadBooks();
  renderBookPanel();
  renderBookInspector();
}

async function deleteBook(bid) {
  const b = BK.list.find(x => x.id === bid);
  const name = b ? b.title : '这本书';
  if (!confirm('删除《' + name + '》？\n\n所有章节、设定库、历史版本都会一起删掉，不能撤销。')) return;
  try {
    await api('DELETE', '/api/books/' + bid);
    if (S.bookId === bid) {
      BK.book = null;
      BK.chapter = null;
      S.bookId = null;
      S.chapterId = null;
      showChapterEmpty();
      setBookHeader('', true);
      $('#bookMeta').textContent = '';
    }
    await loadBooks();
    renderBookPanel();
    renderBookInspector();
    toast('已删除《' + name + '》');
  } catch (e) { toast('删除失败：' + e.message); }
}

async function pickBookFile() {
  if (hasBridge() && window.pywebview && window.pywebview.api &&
      window.pywebview.api.pick_doc_file) {
    try {
      const r = await window.pywebview.api.pick_doc_file();
      if (!r || !r.ok) { if (r && r.message) toast(r.message); return; }
      doBookImport(r.name, r.data);
      return;
    } catch (_) { }
  }
  const f = $('#fileBook');
  if (f) f.click();
}

async function deleteChapter(cid) {
  const c = (BK.book.chapters || []).find(x => x.id === cid);
  if (!c) return;
  if (!confirm('删除「' + c.title + '」？正文会一起删掉，不能撤销。')) return;
  try {
    await api('DELETE', '/api/books/' + S.bookId + '/chapters/' + cid);
    if (S.chapterId === cid) {
      BK.chapter = null;
      S.chapterId = null;
      showChapterEmpty();
    }
    await refreshBook();
    toast('已删除');
  } catch (e) { toast('删除失败：' + e.message); }
}

function newVolume() {
  const vols = (BK.book.book.volumes || []).length + 1;
  openSheet('新建卷', '');
  $('#sheetBody').innerHTML = '<div class="field"><label>卷名</label>' +
    '<input class="input" id="volTitle" placeholder="第' + vols + '卷　卷名"></div>' +
    '<div class="plain" style="color:var(--muted);margin-top:10px">' +
    '建好之后，把章节拖进这一卷就行。</div>';
  $('#sheetFoot').innerHTML = '<div class="spacer"></div><button class="primary" id="volSave">新建</button>';
  $('#volSave').onclick = async () => {
    const t = ($('#volTitle').value || '').trim() || ('第' + vols + '卷');
    const vs = BK.book.book.volumes || (BK.book.book.volumes = []);
    vs.push({ id: 'v' + Date.now().toString(36), title: t, chapters: [] });
    try {
      await api('PATCH', '/api/books/' + S.bookId, { volumes: vs });
      closeSheet();
      await refreshBook();
      toast('已新建 ' + t);
    } catch (e) { toast('新建失败：' + e.message); }
  };
}

function shortTitle(c) {
  const t = String(c.title || '');
  const s = t.replace(/^第\s*[0-9零一二三四五六七八九十百千两]+\s*[章回节卷][\s　·、]*/, '');
  return s || t;
}

function chItemHtml(c) {
  const hasSum = c.summary ? '<i class="dot-ok" title="已有摘要"></i>' : '';
  const drift = ((BK.book && BK.book.drift) || []).some(d => d.chapterId === c.id);
  const driftDot = drift ? '<i class="dot-drift" title="提纲改过了，正文还没跟上"></i>' : '';
  return '<div class="ch-item' + (c.id === S.chapterId ? ' active' : '') + '" data-cid="' + c.id + '">' +
    '<span class="no">' + c.no + '</span>' +
    '<span class="t">' + esc(shortTitle(c)) + '</span>' + hasSum + driftDot +
    '<span class="w">' + fmtW(c.words) + '</span>' +
    '<span class="del" data-del="' + c.id + '" title="删除本章">×</span></div>';
}

let dragCid = null;
function clearDropMarks() {
  $$('.ch-item').forEach(e => e.classList.remove('drop-before', 'drop-after'));
}
function bindChapterDrag(el) {
  el.draggable = true;
  el.ondragstart = e => {
    dragCid = el.dataset.cid;
    el.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    try { e.dataTransfer.setData('text/plain', dragCid); } catch (_) { }
  };
  el.ondragend = () => {
    el.classList.remove('dragging');
    clearDropMarks();
    dragCid = null;
  };
  el.ondragover = e => {
    if (!dragCid || dragCid === el.dataset.cid) return;
    e.preventDefault();
    const r = el.getBoundingClientRect();
    const before = (e.clientY - r.top) < r.height / 2;
    clearDropMarks();
    el.classList.add(before ? 'drop-before' : 'drop-after');
  };
  el.ondrop = e => {
    e.preventDefault();
    const target = el.dataset.cid;
    const before = el.classList.contains('drop-before');
    clearDropMarks();
    if (!dragCid || dragCid === target) return;
    moveChapter(dragCid, target, before);
  };
}

async function moveChapter(srcCid, targetCid, before) {
  const vols = BK.book.book.volumes;
  let srcCh = null, srcVol = null, tVol = null;
  vols.forEach(v => {
    v.chapters.forEach(c => {
      if (c.id === srcCid) { srcCh = c; srcVol = v; }
      if (c.id === targetCid) tVol = v;
    });
  });
  if (!srcCh || !tVol) return;
  srcVol.chapters.splice(srcVol.chapters.indexOf(srcCh), 1);
  let idx = tVol.chapters.findIndex(c => c.id === targetCid);
  if (idx < 0) idx = tVol.chapters.length;
  else if (!before) idx += 1;
  tVol.chapters.splice(idx, 0, srcCh);
  try {
    await api('PATCH', '/api/books/' + S.bookId, { volumes: vols });
    await refreshBook();
  } catch (e) { toast('移动失败：' + e.message); }
}

/* ---------------------------------------------- 章节编辑 */
async function openChapter(cid) {
  if (BK.dirty) await saveChapter();
  try {
    const c = await api('GET', '/api/books/' + S.bookId + '/chapters/' + cid);
    BK.chapter = c;
    S.chapterId = cid;
    BK.dirty = false;
    $('#chEmpty').classList.add('hidden');
    $('#chBody').classList.remove('hidden');
    $('#chTitle').value = c.title || '';
    $('#chText').value = c.text || '';
    updateWords();
    $$('.ch-item').forEach(e => e.classList.toggle('active', e.dataset.cid === cid));
    $('#chStatus').classList.remove('show');
    renderBookInspector();
    const sc = $('#chText');
    sc.scrollTop = 0;
  } catch (e) { toast('打开章节失败：' + e.message); }
}

function markDirty() {
  BK.dirty = true;
  updateWords();
  const st = $('#chStatus');
  st.textContent = '未保存…';
  st.classList.add('show');
  clearTimeout(BK.timer);
  BK.timer = setTimeout(() => saveChapter(), 1200);
}

async function saveChapter() {
  if (!BK.chapter || !BK.dirty) return;
  BK.dirty = false;
  const text = $('#chText').value;
  const title = $('#chTitle').value;
  try {
    const r = await api('PUT', '/api/books/' + S.bookId + '/chapters/' + BK.chapter.id,
      { text, title });
    BK.chapter.text = text;
    BK.chapter.title = title;
    BK.chapter.words = r.words || countChars(text);
    const st = $('#chStatus');
    st.textContent = '已保存 · ' + fmtW(BK.chapter.words) + ' 字';
    setTimeout(() => st.classList.remove('show'), 1500);
    const it = document.querySelector('.ch-item[data-cid="' + BK.chapter.id + '"] .w');
    if (it) it.textContent = fmtW(BK.chapter.words);
    if (BK.book) {
      const c = BK.book.chapters.find(x => x.id === BK.chapter.id);
      if (c) { c.words = BK.chapter.words; c.title = title; }
      BK.book.stats.words = (BK.book.chapters || []).reduce((s, x) => s + (x.words || 0), 0);
      renderBookMeta();
    }
  } catch (e) {
    BK.dirty = true;
    const st = $('#chStatus');
    st.textContent = '保存失败：' + e.message;
    st.classList.add('show');
  }
}

async function newChapter() {
  if (!S.bookId) return;
  if (BK.dirty) await saveChapter();
  const b = BK.book && BK.book.book;
  const vol = b && b.volumes && b.volumes[b.volumes.length - 1];
  try {
    const r = await api('POST', '/api/books/' + S.bookId + '/chapters',
      { volumeId: vol ? vol.id : null });
    await refreshBook();
    await openChapter(r.id);
    $('#chTitle').focus();
    $('#chTitle').select();
    setTimeout(() => toast('点右上「提纲」可以套用章节模板', 3000), 600);
  } catch (e) { toast('新建失败：' + e.message); }
}

/* ---------------------------------------------- 右栏 */
function renderBookInspector() {
  const box = $('#inspector');
  if (!box) return;
  if (!BK.book) {
    box.innerHTML = '<div class="insp-sec"><div class="insp-label">书稿</div>' +
      '<div class="insp-sub">选一本，或新建一本。</div></div>';
    return;
  }
  const st = BK.book.stats || {};
  const b = BK.book.book;
  let html = '<div class="insp-sec">' +
    '<div class="insp-label">本书</div>' +
    '<div class="insp-title">' + esc(b.title) + '</div>' +
    '<div class="insp-sub">' + (st.volumes || 0) + ' 卷 · ' + (st.chapters || 0) + ' 章 · ' +
    fmtW(st.words || 0) + ' 字</div></div>';
  html += '<div class="insp-tabs">' +
    '<button class="insp-tab' + (BK.tab === 'bible' ? ' on' : '') + '" data-tab="bible">设定</button>' +
    '<button class="insp-tab' + (BK.tab === 'search' ? ' on' : '') + '" data-tab="search">检索</button>' +
    '<button class="insp-tab' + (BK.tab === 'stats' ? ' on' : '') + '" data-tab="stats">统计</button>' +
    '</div><div id="inspPane"></div>';
  box.innerHTML = html;
  box.querySelectorAll('.insp-tab').forEach(el => {
    el.onclick = () => { BK.tab = el.dataset.tab; renderBookInspector(); };
  });
  renderInspPane();
}

function renderInspPane() {
  const pane = $('#inspPane');
  if (!pane) return;
  if (BK.tab === 'search') return renderSearchPane(pane);
  if (BK.tab === 'stats') return renderStatsPane(pane);
  return renderBiblePane(pane);
}

function renderBiblePane(pane) {
  const bi = (BK.book && BK.book.bible) || {};
  const sec = (title, items, type, empty) => {
    let h = '<div class="bible-h">' + title + '<span class="n">' + items.length + '</span>' +
      '<button class="mini" data-add="' + type + '">+</button></div>';
    if (!items.length) return h + '<div class="bible-empty">' + empty + '</div>';
    h += items.map((it, i) => {
      const name = it.name || it.main || it.title || '未命名';
      let sub = '';
      if (type === 'characters') sub = it.identity || '';
      else if (type === 'factions') sub = it.type || '';
      else if (type === 'items') sub = it.owner || '';
      else if (type === 'foreshadow') sub = it.status === 'done' ? '已收' : (it.payoffChapter ? '待收' : '未收');
      else if (type === 'terms') sub = (it.aliases || []).length ? (it.aliases || []).length + ' 别名' : '';
      return '<div class="bible-item" data-type="' + type + '" data-i="' + i + '">' +
        '<span class="nm">' + esc(name) + '</span>' +
        (sub ? '<span class="sub">' + esc(sub) + '</span>' : '') + '</div>';
    }).join('');
    return h;
  };
  let html = '<div class="insp-pane">';
  html += sec('人物', bi.characters || [], 'characters', '还没有人物卡。点 + 加一个，或者从正文抽。');
  html += sec('势力', bi.factions || [], 'factions', '还没有势力。');
  html += sec('道具', bi.items || [], 'items', '还没有道具。');
  html += sec('伏笔', bi.foreshadow || [], 'foreshadow', '还没有伏笔记录。');
  html += sec('名词表', bi.terms || [], 'terms', '名词表用来查「老王 / 王大哥」这种叫法不一致。');
  html += '<div class="bible-h">世界观<button class="mini" data-add="world">编辑</button></div>';
  html += bi.world
    ? '<div class="bible-empty" style="color:var(--ink-3)">' + esc(bi.world.slice(0, 160)) +
    (bi.world.length > 160 ? '…' : '') + '</div>'
    : '<div class="bible-empty">还没有写世界观。</div>';
  html += '<div class="bible-h">工具</div>';
  html += '<div class="bible-item" data-act="scan">从正文抽人名</div>';
  html += '<div class="bible-item" data-act="terms">名词统一检查</div>';
  html += '<div class="bible-item" data-act="foreshadow">伏笔回收检查</div>';
  html += '<div class="bible-item" data-act="relations">生成人物关系图</div>';
  html += '</div>';
  pane.innerHTML = html;

  pane.querySelectorAll('[data-add]').forEach(el => {
    el.onclick = () => {
      const t = el.dataset.add;
      if (t === 'world') return openWorldEditor();
      openBibleEditor(t, -1);
    };
  });
  pane.querySelectorAll('.bible-item[data-type]').forEach(el => {
    el.onclick = () => openBibleEditor(el.dataset.type, +el.dataset.i);
  });
  pane.querySelectorAll('[data-act]').forEach(el => {
    el.onclick = () => bibleAction(el.dataset.act);
  });
}

/* ---------------------------------------------- 设定库编辑器 */
const TYPE_LABEL = {
  characters: '人物', factions: '势力', items: '道具',
  foreshadow: '伏笔', terms: '名词',
};

const BIBLE_FIELDS = {
  characters: [
    ['name', '姓名', 'input', '林昭'],
    ['aliases', '别名', 'input', '用顿号或逗号分隔：昭儿、小林'],
    ['age', '年龄', 'input', '19'],
    ['gender', '性别', 'input', '男 / 女'],
    ['identity', '身份', 'input', '青崖城捕快'],
    ['appearance', '外貌', 'textarea', '身高、特征、常穿什么。写具体的，别写「英俊」'],
    ['personality', '性格', 'textarea', '欲望 / 恐惧 / 底线 / 会为什么破例'],
    ['speech', '说话方式', 'textarea', '口头禅、句长、对长辈和下属分别怎么称呼'],
    ['faction', '阵营', 'input', ''],
    ['relations', '关系', 'textarea', '每行一条：对象|关系|备注'],
    ['notes', '备注', 'textarea', ''],
  ],
  factions: [
    ['name', '名称', 'input', ''],
    ['type', '类型', 'input', '门派 / 官府 / 商会'],
    ['goal', '目的', 'textarea', ''],
    ['members', '成员', 'input', '逗号分隔'],
    ['notes', '备注', 'textarea', ''],
  ],
  items: [
    ['name', '名称', 'input', ''],
    ['owner', '持有者', 'input', ''],
    ['desc', '说明', 'textarea', '来历、能力、代价'],
    ['notes', '备注', 'textarea', ''],
  ],
  foreshadow: [
    ['title', '伏笔', 'input', '一句话说清埋了什么'],
    ['plantChapter', '埋设章号', 'input', '第几章埋的'],
    ['payoffChapter', '回收章号', 'input', '计划第几章收'],
    ['status', '状态', 'input', 'open / done'],
    ['note', '说明', 'textarea', '打算怎么收'],
  ],
  terms: [
    ['main', '正名', 'input', '统一用哪个叫法'],
    ['aliases', '别名', 'input', '其他叫法，逗号分隔'],
    ['type', '类型', 'input', 'person / place / org / item / title'],
    ['note', '备注', 'input', ''],
  ],
};

const DRAWER_DEFAULT_ACTS = '<button class="ghost" id="btnClearProject">清空</button>';

function openDrawer(title, sub, body, acts) {
  $('#drawerTitle').textContent = title;
  $('#drawerSub').textContent = sub;
  const ss = $('#saveState');
  if (ss) ss.textContent = S.view === 'book' ? '' : '自动保存';
  $('#projectForm').innerHTML = body;
  $('#drawerActs').innerHTML = acts || DRAWER_DEFAULT_ACTS;
  $('#drawer').classList.add('open');
  $('#drawerMask').classList.add('show');
}

function closeDrawer() {
  $('#drawer').classList.remove('open');
  $('#drawerMask').classList.remove('show');
}

let editingBible = null;

function openBibleEditor(type, idx) {
  const bi = BK.book.bible;
  if (!Array.isArray(bi[type])) bi[type] = [];
  const item = idx >= 0 ? bi[type][idx] : {};
  const fields = BIBLE_FIELDS[type];
  let html = '';
  fields.forEach(([k, label, kind, ph]) => {
    let v = item[k];
    if (Array.isArray(v)) {
      if (k === 'relations') {
        v = v.map(r => [r.to || '', r.type || '', r.note || ''].join('|')).join('\n');
      } else {
        v = v.join('、');
      }
    }
    v = v == null ? '' : String(v);
    html += '<div class="field"><label>' + label + '</label>';
    html += kind === 'textarea'
      ? '<textarea class="textarea" data-f="' + k + '" placeholder="' + esc(ph || '') + '">' + esc(v) + '</textarea>'
      : '<input class="input" data-f="' + k + '" value="' + esc(v) + '" placeholder="' + esc(ph || '') + '">';
    html += '</div>';
  });
  const acts = (idx >= 0 ? '<button class="ghost" id="bibleDel">删除</button>' : '') +
    '<button class="primary" id="bibleSave">保存</button>';
  openDrawer(TYPE_LABEL[type] + (idx >= 0 ? ' · 编辑' : ' · 新建'),
    '写作时会按需注入这些设定，不用一次全塞给模型。', html, acts);
  editingBible = { type, idx };

  $('#bibleSave').onclick = () => saveBibleItem();
  const del = $('#bibleDel');
  if (del) del.onclick = () => {
    if (!confirm('删除这一条？')) return;
    bi[type].splice(idx, 1);
    pushBible();
    closeDrawer();
  };
}

function collectBibleForm() {
  const o = {};
  $$('#projectForm [data-f]').forEach(el => {
    const k = el.dataset.f;
    let v = el.value;
    if (k === 'aliases') {
      v = v.split(/[、,，\s]+/).map(x => x.trim()).filter(Boolean);
    } else if (k === 'relations') {
      v = v.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
        const p = l.split('|').map(x => (x || '').trim());
        return { to: p[0] || '', type: p[1] || '', note: p[2] || '' };
      });
    }
    o[k] = v;
  });
  return o;
}

async function saveBibleItem() {
  if (!editingBible) return;
  const { type, idx } = editingBible;
  const data = collectBibleForm();
  if (!(data.name || data.main || data.title)) return toast('名称不能为空');
  const list = BK.book.bible[type];
  if (idx >= 0) list[idx] = Object.assign({}, list[idx], data);
  else list.push(data);
  await pushBible();
  closeDrawer();
  toast('已保存');
}

async function pushBible() {
  try {
    await api('PUT', '/api/books/' + S.bookId + '/bible', BK.book.bible);
    renderBookInspector();
  } catch (e) { toast('保存失败：' + e.message); }
}

function openWorldEditor() {
  const w = (BK.book.bible && BK.book.bible.world) || '';
  openDrawer('世界观与规则', '硬规则、代价、地理、时代考据。写清「什么不可能发生」。',
    '<div class="field"><textarea class="textarea" id="worldText" style="min-height:320px" ' +
    'placeholder="力量体系与代价 / 势力格局 / 地理与交通 / 时代与技术 / 禁忌">' + esc(w) + '</textarea></div>',
    '<button class="primary" id="worldSave">保存</button>');
  $('#worldSave').onclick = async () => {
    BK.book.bible.world = $('#worldText').value;
    await pushBible();
    closeDrawer();
    toast('已保存');
  };
}

/* ---------------------------------------------- 设定库工具 */
async function bibleAction(act) {
  if (!S.bookId) return;
  if (act === 'scan') {
    openSheet('从正文抽人名', '正在扫全书…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/names', { limit: 60 });
      const names = d.names || [];
      if (!names.length) { $('#sheetBody').textContent = '没抽出候选名。可能是正文太短。'; return; }
      const have = new Set((BK.book.bible.characters || []).map(c => c.name));
      $('#sheetBody').innerHTML = '<div class="plain" style="color:var(--muted);margin-bottom:10px">' +
        '按出现次数排序。勾选后加进人物卡。</div>' +
        names.map((n, i) =>
          '<label class="bible-item" style="cursor:pointer">' +
          '<input type="checkbox" data-ni="' + i + '"' + (have.has(n.name) ? ' checked disabled' : '') + '>' +
          '<span class="nm">' + esc(n.name) + '</span>' +
          '<span class="sub">' + n.count + ' 次 · 首见第' + (n.firstChapter || '?') + '章</span></label>'
        ).join('');
      $('#sheetFoot').innerHTML = '<span class="plain" id="scanNote" style="color:var(--muted)"></span>' +
        '<div class="spacer"></div><button class="primary" id="scanAdd">加入人物卡</button>';
      $('#scanAdd').onclick = async () => {
        const picked = $$('#sheetBody input[data-ni]:checked').map(el => names[+el.dataset.ni]);
        if (!picked.length) return toast('没选');
        picked.forEach(n => BK.book.bible.characters.push({
          name: n.name, aliases: [], identity: '', notes: '首见第' + (n.firstChapter || '?') + '章',
        }));
        await pushBible();
        closeSheet();
        toast('已加入 ' + picked.length + ' 个');
      };
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
    return;
  }

  if (act === 'terms') {
    openSheet('名词统一检查', '正在比对名词表…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/check', { kind: 'terms' });
      const r = d.result || {};
      const issues = r.issues || [];
      if (!issues.length) {
        $('#sheetBody').innerHTML = '<div class="plain" style="color:var(--muted)">' +
          '名词表里 ' + (r.known || 0) + ' 个名称，没有发现叫法混用。' +
          (r.known ? '' : '（名词表是空的，先在右边加几条）') + '</div>';
        return;
      }
      $('#sheetBody').innerHTML = issues.map(i =>
        '<div class="sheet-issue high"><div class="si-h">' + esc(i.term) + '</div>' +
        '<div class="si-w">同一实体用了不同叫法：' + esc(i.detail) + '</div></div>').join('');
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
    return;
  }

  if (act === 'foreshadow') {
    openSheet('伏笔回收检查', '正在对全书…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/check', { kind: 'foreshadow' });
      const items = d.items || [];
      if (!items.length) { $('#sheetBody').textContent = '设定库里还没有伏笔记录。'; return; }
      $('#sheetBody').innerHTML = items.map(f =>
        '<div class="sheet-issue' + (f.warn ? ' high' : '') + '">' +
        '<div class="si-h">' + esc(f.title) + ' <span style="font-weight:400;color:var(--muted)">' +
        (f.status === 'done' ? '已回收' : (f.payoff ? '计划第' + f.payoff + '章收' : '未安排回收')) + '</span></div>' +
        '<div class="si-w">埋设：' + (f.plant ? '第' + f.plant + '章' : '未记录') +
        ' · 正文命中：' + ((f.foundIn || []).length ? '第' + f.foundIn.join('、') + '章' : '没找到原句') + '</div>' +
        (f.warn ? '<div class="si-f" style="color:var(--accent)">埋了 30 章以上还没收，读者可能已经忘了</div>' : '') +
        '</div>').join('');
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
    return;
  }

  if (act === 'relations') {
    openSheet('人物关系图', '正在整理…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/relations', {});
      BK.graph = d.graph;
      renderGraphSheet(d.graph);
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
  }
}

/* ---------------------------------------------- 检索 */
function renderSearchPane(pane) {
  pane.innerHTML = '<div class="search-box"><input id="bkSearch" placeholder="搜片段 / 人名 / 伏笔…"></div>' +
    '<div id="bkHits"></div>';
  const inp = $('#bkSearch');
  if (BK.lastQuery) inp.value = BK.lastQuery;
  inp.onkeydown = e => {
    if (e.key === 'Enter') { e.preventDefault(); doSearch(inp.value); }
  };
  renderHits();
}

async function doSearch(q) {
  q = (q || '').trim();
  if (!q || !S.bookId) return;
  BK.lastQuery = q;
  const box = $('#bkHits');
  if (box) box.innerHTML = '<div class="bible-empty">检索中…</div>';
  try {
    const d = await api('POST', '/api/books/' + S.bookId + '/search', { query: q, k: 12 });
    BK.hits = d.hits || [];
    BK.locate = null;
    if (q.length >= 2 && q.length <= 6) {
      api('POST', '/api/books/' + S.bookId + '/locate', { name: q })
        .then(r => { BK.locate = r; renderHits(); }).catch(() => { });
    }
    renderHits();
  } catch (e) {
    if (box) box.innerHTML = '<div class="bible-empty">' + esc(e.message) + '</div>';
  }
}

function renderHits() {
  const box = $('#bkHits');
  if (!box) return;
  let html = '';
  if (BK.locate && BK.locate.total) {
    html += '<div class="bible-empty" style="color:var(--accent-ink)">' +
      '「' + esc(BK.locate.name) + '」首次出现在第 ' + BK.locate.first.no + ' 章，全书 ' +
      BK.locate.total + ' 次，分布在 ' + BK.locate.hits.length + ' 章</div>';
  }
  if (!BK.hits.length) {
    box.innerHTML = html + (html ? '' : '<div class="bible-empty">没有结果。</div>');
    return;
  }
  html += BK.hits.map(h =>
    '<div class="hit" data-cid="' + h.chapterId + '">' +
    '<div class="hit-h">第 ' + h.no + ' 章' + (shortTitle(h) ? ' · ' + esc(shortTitle(h)) : '') + '</div>' +
    '<div class="hit-s">' + esc(h.snippet) + '</div></div>').join('');
  box.innerHTML = html;
  box.querySelectorAll('.hit').forEach(el => {
    el.onclick = () => { openChapter(el.dataset.cid); };
  });
}

/* ---------------------------------------------- 统计 */
function renderStatsPane(pane) {
  pane.innerHTML = '<div class="insp-pane">' +
    '<div class="bible-h">全书</div><div id="stkBody"></div>' +
    '<div class="bible-h">大纲</div>' +
    '<div class="bible-item" data-sact="outlineBook">全书大纲</div>' +
    '<div class="bible-item" data-sact="outlineVol">本卷大纲</div>' +
    '<div class="bible-h">工具</div>' +
    '<div class="bible-item" data-sact="rhythm">情绪节奏分析</div>' +
    '<div class="bible-item" data-sact="sumAll">批量生成章节摘要</div>' +
    '<div class="bible-item" data-sact="sumVol">生成本卷摘要</div>' +
    '<div class="bible-item" data-sact="sumBook">生成全书梗概</div>' +
    '<div class="bible-item" data-sact="branch">剧情分支推演</div>' +
    '</div>';
  const st = (BK.book && BK.book.stats) || {};
  $('#stkBody').innerHTML =
    '<div class="bible-empty" style="color:var(--ink-3)">' +
    '字数 ' + fmtW(st.words || 0) + ' · 章节 ' + (st.chapters || 0) + ' · 卷 ' + (st.volumes || 0) + '<br>' +
    '人物 ' + (st.characters || 0) + ' · 未回收伏笔 ' + (st.openForeshadow || 0) + '</div>';
  pane.querySelectorAll('[data-sact]').forEach(el => {
    el.onclick = () => statsAction(el.dataset.sact);
  });
}

async function batchSummarize() {
  const chs = (BK.book.chapters || []).filter(c => !c.summary && c.words > 0);
  if (!chs.length) return toast('所有章节都已有摘要');
  BK.batchCancel = false;
  openSheet('批量生成摘要', '准备中…');
  let done = 0, failed = 0;
  for (const c of chs) {
    if (BK.batchCancel) break;
    $('#sheetBody').innerHTML = '<div class="plain">进度 ' + done + ' / ' + chs.length +
      ' 章　<span style="color:var(--muted)">正在处理：' + esc(c.title) + '</span></div>';
    try {
      await api('POST', '/api/books/' + S.bookId + '/summarize',
        { scope: 'chapter', ids: [c.id] });
      done++;
    } catch (e) {
      failed++;
      if (failed === 1) {
        $('#sheetBody').innerHTML += '<div style="color:var(--accent);margin-top:8px">' +
          '第' + c.no + '章失败：' + esc(e.message) + '</div>';
        break;
      }
    }
  }
  await refreshBook();
  if (BK.batchCancel) return;
  $('#sheetBody').innerHTML = '<div class="plain">完成 ' + done + ' / ' + chs.length + ' 章' +
    (failed ? '，' + failed + ' 章失败' : '') + '。' +
    (done ? '<br><br><span style="color:var(--muted)">现在可以生成本卷摘要或全书梗概了。</span>' : '') +
    '</div>';
}

function openOutlineEditor(scope) {
  const cur = (BK.book.chapters || []).find(c => c.id === S.chapterId);
  const vs = BK.book.book.volumes || [];
  const vol = cur ? vs.find(x => x.id === cur.volumeId) : vs[0];
  if (scope === 'volume' && !vol) return toast('先建一卷');
  const ol = BK.book.outline || { book: '', volumes: {} };
  const text = scope === 'book' ? (ol.book || '') : ((ol.volumes || {})[vol.id] || '');
  const key = scope === 'book' ? '' : vol.id;
  openDrawer(scope === 'book' ? '全书大纲' : '本卷大纲 · ' + vol.title,
    '改完大纲后，没跟上改动的章节会在左栏标一个橙点。',
    tplChips('outline') +
    '<div class="field"><textarea class="textarea" id="olText" style="min-height:360px" ' +
    'placeholder="' + (scope === 'book'
      ? '分卷结构、主线推进、关键转折、结局落在哪'
      : '这一卷从哪开始、推到哪、卷末留什么') + '">' + esc(text) + '</textarea></div>' +
    '<div class="tpl-hint">结构模板会把百分比和章节号位置留空，填完就是一张可执行的路线图。</div>',
    '<button class="primary" id="olSave">保存</button>');
  bindTplChips('outline', $('#olText'));
  $('#olSave').onclick = async () => {
    const v = $('#olText').value;
    try {
      await api('PUT', '/api/books/' + S.bookId + '/outline',
        { scope, key, text: v });
      if (scope === 'book') BK.book.outline.book = v;
      else {
        BK.book.outline.volumes = BK.book.outline.volumes || {};
        BK.book.outline.volumes[key] = v;
      }
      closeDrawer();
      toast('已保存');
      refreshBook();
    } catch (e) { toast('保存失败：' + e.message); }
  };
}

async function statsAction(act) {
  if (act === 'outlineBook') return openOutlineEditor('book');
  if (act === 'outlineVol') return openOutlineEditor('volume');
  if (act === 'sumAll') return batchSummarize();
  if (act === 'rhythm') {
    openSheet('情绪节奏分析', '正在统计…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/check', { kind: 'rhythm' });
      const list = d.chapters || [];
      if (!list.length) { $('#sheetBody').textContent = '没有正文可分析。'; return; }
      const avgD = list.reduce((s, x) => s + x.dialogue, 0) / list.length;
      const avgS = list.reduce((s, x) => s + x.scene, 0) / list.length;
      let html = '<div class="plain" style="color:var(--muted);margin-bottom:12px">' +
        '全书对话占比 ' + (avgD * 100).toFixed(1) + '%，场景描写占比 ' + (avgS * 100).toFixed(1) + '%。' +
        '某章明显偏离，通常是节奏出了问题。</div>';
      html += '<div class="plain">';
      list.forEach(x => {
        const dDev = x.dialogue - avgD;
        const mark = Math.abs(dDev) > 0.18 ? (dDev > 0 ? '（对话偏多）' : '（对话偏少）') : '';
        html += '<div class="bible-item" style="cursor:pointer" data-cid="' + x.chapterId + '">' +
          '<span class="nm">第' + x.no + '章 ' + esc(x.title) + '</span>' +
          '<span class="sub">' + fmtW(x.words) + '字 · 对话 ' + (x.dialogue * 100).toFixed(0) + '%' +
          ' · 描写 ' + (x.scene * 100).toFixed(0) + '%' + mark + '</span></div>';
      });
      html += '</div>';
      $('#sheetBody').innerHTML = html;
      $('#sheetBody').querySelectorAll('[data-cid]').forEach(el => {
        el.onclick = () => { closeSheet(); openChapter(el.dataset.cid); };
      });
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
    return;
  }
  if (act === 'sumVol' || act === 'sumBook') {
    const scope = act === 'sumVol' ? 'volume' : 'book';
    openSheet(scope === 'volume' ? '本卷摘要' : '全书梗概', '正在汇总各章摘要…');
    try {
      const body = { scope };
      if (scope === 'volume') {
        const cur = (BK.book.chapters || []).find(c => c.id === S.chapterId);
        const vs = BK.book.book.volumes || [];
        const v = cur ? vs.find(x => x.id === cur.volumeId) : vs[0];
        body.volumeId = v ? v.id : '';
      }
      const d = await api('POST', '/api/books/' + S.bookId + '/summarize', body);
      $('#sheetBody').textContent = d.text || '';
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
    return;
  }
  if (act === 'branch') {
    openSheet('剧情分支推演', '正在推演…');
    try {
      const d = await api('POST', '/api/books/' + S.bookId + '/branch',
        { chapterId: S.chapterId, situation: '' });
      const bs = d.branches || [];
      if (!bs.length) { $('#sheetBody').textContent = '没有推演出分支。'; return; }
      $('#sheetBody').innerHTML = bs.map((b, i) =>
        '<div class="sheet-issue' + (i === 0 ? ' high' : '') + '">' +
        '<div class="si-h">' + esc(b.title || ('走向 ' + (i + 1))) +
        ' <span style="font-weight:400;color:var(--muted)">结构分 ' + (b.score || '-') + '/5</span></div>' +
        '<div class="si-q">' + esc(b.scene || '') + '</div>' +
        '<div class="si-w">怎么长出来的：' + esc(b.logic || '') + '</div>' +
        '<div class="si-w">代价：' + esc(b.cost || '') + '</div>' +
        '<div class="si-f">可收伏笔：' + esc(((b.foreshadow || {}).recover || []).join('、') || '无') +
        ' · 新埋：' + esc(((b.foreshadow || {}).new || []).join('、') || '无') + '</div></div>').join('');
    } catch (e) { $('#sheetBody').textContent = '失败：' + e.message; }
  }
}

/* ---------------------------------------------- 关系图 */
function renderGraphSheet(g) {
  const nodes = (g && g.nodes) || [];
  const edges = (g && g.edges) || [];
  if (!nodes.length) { $('#sheetBody').textContent = '没有生成出关系。先在设定库里加人物。'; return; }
  const W = 660, H = 460, cx = W / 2, cy = H / 2;
  const R = Math.min(cx, cy) - 74;
  const pos = {};
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    pos[n.id] = { x: cx + Math.cos(a) * R, y: cy + Math.sin(a) * R };
  });
  let svg = '<div style="width:100%;height:min(50vh,430px)">' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet" ' +
    'style="display:block;width:100%;height:100%">';
  edges.forEach(e => {
    const a = pos[e.from], b = pos[e.to];
    if (!a || !b) return;
    const w = Math.max(0.8, Math.min(3.2, (e.weight || 2) * 0.55));
    svg += '<line x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y +
      '" stroke="var(--line)" stroke-width="' + w + '"/>';
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    if (e.type) {
      svg += '<text x="' + mx + '" y="' + my + '" font-size="9.5" fill="var(--muted)" ' +
        'text-anchor="middle" dy="-4">' + esc(e.type) + '</text>';
    }
  });
  nodes.forEach(n => {
    const p = pos[n.id];
    const r = 19;
    svg += '<circle cx="' + p.x + '" cy="' + p.y + '" r="' + r +
      '" fill="var(--surface-solid)" stroke="var(--accent)" stroke-width="1.3"/>';
    svg += '<text x="' + p.x + '" y="' + (p.y + 4.5) + '" font-size="13" fill="var(--ink)" ' +
      'text-anchor="middle">' + esc(String(n.id).slice(0, 1)) + '</text>';
    svg += '<text x="' + p.x + '" y="' + (p.y + r + 13) + '" font-size="10.5" fill="var(--ink-2)" ' +
      'text-anchor="middle">' + esc(n.id) + '</text>';
  });
  svg += '</svg></div>';
  $('#sheetBody').innerHTML = svg;
  $('#sheetFoot').innerHTML = '<span class="plain" style="color:var(--muted)">' +
    nodes.length + ' 人 · ' + edges.length + ' 条关系</span><div class="spacer"></div>';
}

/* ---------------------------------------------- 底部面板 */
function openSheet(title, content) {
  $('#sheetTitle').textContent = title;
  $('#sheetBody').textContent = content || '';
  $('#sheetFoot').innerHTML = '<div class="spacer"></div>';
  $('#sheetMask').classList.add('show');
  $('#sheet').classList.add('open');
}

function closeSheet() {
  BK.batchCancel = true;
  $('#sheet').classList.remove('open');
  $('#sheetMask').classList.remove('show');
}

function copyText(t) {
  const done = () => toast('已复制');
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(done, () => fallbackCopy(t, done));
  } else {
    fallbackCopy(t, done);
  }
}
function fallbackCopy(t, done) {
  const ta = document.createElement('textarea');
  ta.value = t;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (_) { }
  ta.remove();
  done();
}

/* ---------------------------------------------- 流式写作 */
async function streamBook(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.error || ('请求失败 ' + res.status));
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '', acc = '';
  const el = $('#sheetBody');
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split('\n\n');
    buf = parts.pop() || '';
    for (const p of parts) {
      const evm = /^event: (.+)$/m.exec(p);
      const dtm = /^data: ([\s\S]+)$/m.exec(p);
      if (!evm || !dtm) continue;
      let data;
      try { data = JSON.parse(dtm[1]); } catch (_) { continue; }
      if (evm[1] === 'delta') {
        acc += data.text || '';
        el.textContent = acc;
        el.scrollTop = el.scrollHeight;
      } else if (evm[1] === 'error') {
        el.textContent = acc + '\n\n[出错] ' + (data.message || '');
      }
    }
  }
  return acc;
}

const WRITE_TITLE = {
  continue: '续写本章', polish: '润色', expand: '扩写',
  condense: '压缩', pov: '换视角重写', dialog: '优化对话',
};

async function bookWrite(mode) {
  if (!BK.chapter) return toast('先选一章');
  if (BK.dirty) await saveChapter();
  const ta = $('#chText');
  const sel = ta.value.slice(ta.selectionStart, ta.selectionEnd);
  const body = { chapterId: BK.chapter.id, mode };
  if (mode !== 'continue') {
    if (!sel.trim()) return toast('先在正文里选中一段');
    body.text = sel;
    if (mode === 'pov') {
      const who = window.prompt('用谁的视角重写？输入人物名', '');
      if (!who) return;
      body.persona = who;
    }
  }
  openSheet(WRITE_TITLE[mode] || '生成', '');
  $('#sheetFoot').innerHTML =
    '<span class="plain" id="wrNote" style="color:var(--muted)">生成中…</span>' +
    '<div class="spacer"></div>' +
    (mode === 'continue'
      ? '<button class="primary" id="wrInsert">接到章末</button>'
      : '<button class="primary" id="wrReplace">替换选中</button>') +
    '<button class="ghost" id="wrCopy">复制</button>';
  try {
    const text = await streamBook('/api/books/' + S.bookId + '/write', body);
    const note = $('#wrNote');
    if (note) note.textContent = text.length + ' 字';
    const ins = $('#wrInsert');
    if (ins) ins.onclick = () => { appendToChapter(text); closeSheet(); };
    const rep = $('#wrReplace');
    if (rep) rep.onclick = () => { replaceSelection(text); closeSheet(); };
    const cp = $('#wrCopy');
    if (cp) cp.onclick = () => copyText(text);
  } catch (e) {
    $('#sheetBody').textContent = '失败：' + e.message;
  }
}

function appendToChapter(text) {
  const ta = $('#chText');
  ta.value = ta.value.replace(/\s+$/, '') + '\n\n' + String(text).trim() + '\n';
  markDirty();
  ta.scrollTop = ta.scrollHeight;
}

function replaceSelection(text) {
  const ta = $('#chText');
  const s = ta.selectionStart, e = ta.selectionEnd;
  if (s === e) { toast('选区已失效，已复制'); return copyText(text); }
  ta.value = ta.value.slice(0, s) + String(text).trim() + ta.value.slice(e);
  markDirty();
}

/* ---------------------------------------------- 校验 / 摘要 */
function issueHtml(i) {
  const lv = i.level === 'high' ? ' high' : (i.level === 'low' ? ' low' : '');
  return '<div class="sheet-issue' + lv + '">' +
    '<div class="si-h">' + esc(i.character || '') + ' · ' + esc(i.type || '') + '</div>' +
    (i.quote ? '<div class="si-q">「' + esc(i.quote) + '」</div>' : '') +
    '<div class="si-w">' + esc(i.why || '') + '</div>' +
    (i.fix ? '<div class="si-f">改法：' + esc(i.fix) + '</div>' : '') +
    '</div>';
}

async function bookCheck() {
  if (!BK.chapter) return toast('先选一章');
  if (BK.dirty) await saveChapter();
  openSheet('一致性校验 · ' + BK.chapter.title, '正在拿人物档案比对本章正文…');
  try {
    const d = await api('POST', '/api/books/' + S.bookId + '/check',
      { kind: 'ooc', chapterId: BK.chapter.id });
    const issues = d.issues || [];
    if (!issues.length) {
      $('#sheetBody').innerHTML = '<div class="plain" style="color:var(--muted)">' +
        '没有发现与设定冲突的地方。' + (d.note ? '（' + esc(d.note) + '）' : '') + '</div>';
    } else {
      $('#sheetBody').innerHTML = issues.map(issueHtml).join('');
    }
  } catch (e) {
    $('#sheetBody').textContent = '校验失败：' + e.message;
  }
}

async function bookSummarize() {
  if (!BK.chapter) return toast('先选一章');
  if (BK.dirty) await saveChapter();
  openSheet('章节摘要 · ' + BK.chapter.title, '正在读这一章…');
  try {
    const d = await api('POST', '/api/books/' + S.bookId + '/summarize',
      { scope: 'chapter', ids: [BK.chapter.id] });
    const r = (d.results || [])[0];
    if (!r) { $('#sheetBody').textContent = '没有生成摘要。'; return; }
    const x = r.data || {};
    let html = '<div>' + esc(x.summary || '') + '</div>';
    if ((x.events || []).length) {
      html += '<div class="plain" style="margin-top:14px;color:var(--muted)">关键事件</div>' +
        '<div class="plain">' + x.events.map(e => '· ' + esc(e)).join('<br>') + '</div>';
    }
    if ((x.hooks || []).length) {
      html += '<div class="plain" style="margin-top:14px;color:var(--muted)">本章埋的伏笔</div>' +
        '<div class="plain">' + x.hooks.map(e => '· ' + esc(e)).join('<br>') + '</div>';
    }
    $('#sheetBody').innerHTML = html;
    await refreshBook();
  } catch (e) {
    $('#sheetBody').textContent = '失败：' + e.message;
  }
}

/* ---------------------------------------------- 版本对比 */
function lineDiff(a, b) {
  const la = String(a).split('\n'), lb = String(b).split('\n');
  const n = la.length, m = lb.length;
  if (n * m > 400000) {
    return [{ op: 'del', text: '（改动太大，逐行对比略）' }];
  }
  const dp = [];
  for (let i = 0; i <= n; i++) dp.push(new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = la[i] === lb[j] ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (la[i] === lb[j]) { out.push({ op: 'same', text: la[i] }); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ op: 'del', text: la[i] }); i++; }
    else { out.push({ op: 'add', text: lb[j] }); j++; }
  }
  while (i < n) out.push({ op: 'del', text: la[i++] });
  while (j < m) out.push({ op: 'add', text: lb[j++] });
  return out;
}

function renderDiffHtml(oldText, newText) {
  const rows = lineDiff(oldText, newText);
  const keep = [];
  rows.forEach((r, i) => {
    if (r.op !== 'same') return;
    const near = rows.slice(Math.max(0, i - 2), i + 3).some(x => x.op !== 'same');
    if (near) keep.push(i);
  });
  const set = new Set(keep);
  let html = '<div class="diff">';
  let skipped = 0;
  rows.forEach((r, i) => {
    if (r.op === 'same' && !set.has(i)) { skipped++; return; }
    if (skipped) {
      html += '<div class="ln same">⋯ 略过 ' + skipped + ' 行未改动</div>';
      skipped = 0;
    }
    if (r.op === 'add') html += '<div class="ln add">+ ' + esc(r.text || ' ') + '</div>';
    else if (r.op === 'del') html += '<div class="ln del">- ' + esc(r.text || ' ') + '</div>';
    else html += '<div class="ln same">  ' + esc(r.text || ' ') + '</div>';
  });
  if (skipped) html += '<div class="ln same">⋯ 略过 ' + skipped + ' 行未改动</div>';
  return html + '</div>';
}

/* ---------------------------------------------- 快照 / 提纲 */
async function showSnapshots() {
  if (!BK.chapter) return toast('先选一章');
  openSheet('历史版本 · ' + BK.chapter.title, '读取中…');
  try {
    const d = await api('GET', '/api/books/' + S.bookId + '/snapshots/' + BK.chapter.id);
    const list = d.snapshots || [];
    if (!list.length) {
      $('#sheetBody').innerHTML = '<div class="plain" style="color:var(--muted)">' +
        '还没有历史版本。每次保存时，改动前的正文会自动留一份。</div>';
      return;
    }
    $('#sheetBody').innerHTML = '<div class="plain">' + list.map(s => {
      const dt = new Date(s.ts);
      const pad = n => String(n).padStart(2, '0');
      const label = (dt.getMonth() + 1) + '/' + dt.getDate() + ' ' +
        pad(dt.getHours()) + ':' + pad(dt.getMinutes());
      return '<div class="bible-item" data-ts="' + s.ts + '">' +
        '<span class="nm">' + label + '</span>' +
        '<span class="sub">' + fmtW(s.words) + ' 字</span></div>';
    }).join('') + '</div>';
    $('#sheetBody').querySelectorAll('[data-ts]').forEach(el => {
      el.onclick = () => previewSnapshot(+el.dataset.ts);
    });
  } catch (e) {
    $('#sheetBody').textContent = '读取失败：' + e.message;
  }
}

async function previewSnapshot(ts) {
  try {
    const d = await api('GET', '/api/books/' + S.bookId + '/snapshots/' + BK.chapter.id + '/' + ts);
    const cur = $('#chText').value;
    const old = d.text || '';
    const dt = new Date(ts);
    const pad = n => String(n).padStart(2, '0');
    const label = dt.getFullYear() + '-' + pad(dt.getMonth() + 1) + '-' + pad(dt.getDate()) +
      ' ' + pad(dt.getHours()) + ':' + pad(dt.getMinutes());
    $('#sheetTitle').textContent = '版本 · ' + label;
    $('#sheetBody').textContent = old;
    $('#sheetFoot').innerHTML = '<span class="plain" style="color:var(--muted)">' +
      countChars(old) + ' 字（当前 ' + countChars(cur) + ' 字）</span>' +
      '<div class="spacer"></div>' +
      '<button class="ghost" id="snapBack">回到列表</button>' +
      '<button class="ghost" id="snapDiff">对比当前</button>' +
      '<button class="primary" id="snapRestore">回退到这一版</button>';
    $('#snapBack').onclick = showSnapshots;
    $('#snapDiff').onclick = () => {
      $('#sheetTitle').textContent = '对比 · 这一版 → 当前';
      $('#sheetBody').innerHTML = renderDiffHtml(old, cur);
      $('#sheetFoot').innerHTML = '<span class="plain" style="color:var(--muted)">' +
        '绿色是当前新增，红色是被改掉的原句</span><div class="spacer"></div>' +
        '<button class="ghost" id="snapBack2">回到版本</button>';
      $('#snapBack2').onclick = () => previewSnapshot(ts);
    };
    $('#snapRestore').onclick = async () => {
      if (!confirm('用这一版覆盖当前正文？当前内容会先存成一份快照。')) return;
      try {
        await api('POST', '/api/books/' + S.bookId + '/restore',
          { chapterId: BK.chapter.id, ts });
        await openChapter(BK.chapter.id);
        closeSheet();
        toast('已回退');
      } catch (e) { toast('回退失败：' + e.message); }
    };
  } catch (e) { toast(e.message); }
}

function tplList(kind) {
  if (kind === 'ch') return (typeof CHAPTER_TPL !== 'undefined') ? CHAPTER_TPL : [];
  return (typeof OUTLINE_TPL !== 'undefined') ? OUTLINE_TPL : [];
}

function tplChips(kind) {
  const list = tplList(kind);
  if (!list.length) return '';
  return '<div class="tpl-bar"><span class="tpl-label">套用模板</span>' +
    '<div class="tpl-chips">' +
    list.map(t => '<button class="tpl-chip" data-tpl="' + t.id + '" title="' +
      esc(t.desc) + '">' + esc(t.name) + '</button>').join('') +
    '</div></div>';
}

function bindTplChips(kind, ta) {
  if (!ta) return;
  const list = tplList(kind);
  $$('.tpl-chip').forEach(b => {
    b.onclick = () => {
      const t = list.find(x => x.id === b.dataset.tpl);
      if (!t) return;
      const cur = ta.value.trim();
      ta.value = cur ? (cur + '\n\n---\n\n' + t.body) : t.body;
      ta.focus();
      ta.scrollTop = 0;
      setTimeout(() => { ta.scrollTop = 0; }, 30);
      toast('已插入「' + t.name + '」模板');
    };
  });
}

function openChapterOutline() {
  if (!BK.chapter) return toast('先选一章');
  openDrawer('本章提纲 · ' + BK.chapter.title,
    '提纲会在续写时一并给模型。不知道怎么下手，就挑一个模板。',
    tplChips('ch') +
    '<div class="field"><textarea class="textarea" id="chOutlineText" style="min-height:330px" ' +
    'placeholder="这一章要发生什么：&#10;1. 谁做了什么&#10;2. 冲突卡在哪&#10;3. 结尾留什么钩子">' +
    esc(BK.chapter.outline || '') + '</textarea></div>' +
    '<div class="tpl-hint">模板里的小标题和自检项可以留着，AI 会照着结构写；不想让它看见的提示可以直接删。</div>',
    '<button class="primary" id="chOutlineSave">保存</button>');
  bindTplChips('ch', $('#chOutlineText'));
  $('#chOutlineSave').onclick = async () => {
    const text = $('#chOutlineText').value;
    try {
      await api('PUT', '/api/books/' + S.bookId + '/outline',
        { scope: 'chapter', key: BK.chapter.id, text });
      BK.chapter.outline = text;
      closeDrawer();
      toast('已保存');
    } catch (e) { toast('保存失败：' + e.message); }
  };
}

/* ---------------------------------------------- 导出 / 导入 / 新建 */
function bookExportSheet() {
  if (!S.bookId) return toast('先打开一本');
  openSheet('导出书稿', '');
  $('#sheetBody').innerHTML =
    '<div class="plain" style="color:var(--muted);line-height:2">' +
    'Markdown：带目录和分卷，适合继续加工。<br>' +
    'TXT：纯正文，适合投稿或导入其他工具。<br>' +
    '分章：打包成 zip，一章一个文件，方便再导回知识库。</div>';
  $('#sheetFoot').innerHTML = '<div class="spacer"></div>' +
    '<button class="ghost" id="exMd">Markdown</button>' +
    '<button class="ghost" id="exTxt">TXT</button>' +
    '<button class="primary" id="exZip">分章 zip</button>';
  $('#exMd').onclick = () => doExport('md', false);
  $('#exTxt').onclick = () => doExport('txt', false);
  $('#exZip').onclick = () => doExport('md', true);
}

async function doExport(fmt, split) {
  try {
    const d = await api('POST', '/api/books/' + S.bookId + '/export', { format: fmt, split });
    const bin = atob(d.data);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const blob = new Blob([arr], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = d.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    closeSheet();
    toast('已导出 ' + d.filename);
  } catch (e) { toast('导出失败：' + e.message); }
}

function newBookFlow() {
  openSheet('新建书稿', '');
  const tplOpts = tplList('outline').map(t =>
    '<option value="' + t.id + '">' + esc(t.name) + ' · ' + esc(t.desc) + '</option>').join('');
  $('#sheetBody').innerHTML =
    '<div class="field"><label>书名</label>' +
    '<input class="input" id="nbTitle" placeholder="长夜将尽"></div>' +
    '<div class="field"><label>开局结构（会写进全书大纲，续写时 AI 会照着走）</label>' +
    '<select class="select" id="nbTpl"><option value="">空白 · 自己写大纲</option>' +
    tplOpts + '</select></div>' +
    '<div class="plain" style="color:var(--muted);line-height:2;margin-top:12px">' +
    '空白新建：一章一章写。<br>' +
    '导入整本：把已有的 txt / docx / epub 读进来，按「第X章」自动切分。</div>';
  $('#sheetFoot').innerHTML = '<div class="spacer"></div>' +
    '<button class="ghost" id="nbImport">导入整本</button>' +
    '<button class="primary" id="nbBlank">空白新建</button>';
  $('#nbBlank').onclick = async () => {
    const t = ($('#nbTitle').value || '').trim() || '未命名书稿';
    const tplId = $('#nbTpl') ? $('#nbTpl').value : '';
    try {
      const b = await api('POST', '/api/books', { title: t });
      if (tplId) {
        const tpl = tplList('outline').find(x => x.id === tplId);
        if (tpl) {
          await api('PUT', '/api/books/' + b.id + '/outline',
            { scope: 'book', key: '', text: tpl.body });
        }
      }
      closeSheet();
      await loadBooks();
      await openBook(b.id);
      if (tplId) toast('已套用结构模板，打开「统计 → 全书大纲」填空');
    } catch (e) { toast('新建失败：' + e.message); }
  };
  $('#nbImport').onclick = () => { closeSheet(); pickBookFile(); };
}

function readBookFile(f) {
  const r = new FileReader();
  r.onload = () => doBookImport(f.name, String(r.result).split(',')[1] || '');
  r.readAsDataURL(f);
}

async function doBookImport(name, b64) {
  openSheet('导入书稿', '正在解析并切分章节。30 万字大约几秒。');
  try {
    const d = await api('POST', '/api/books', {
      data: b64, filename: name, title: name.replace(/\.[^.]+$/, ''),
    });
    closeSheet();
    await loadBooks();
    await openBook(d.book.id);
    toast('导入 ' + d.chapters + ' 章');
  } catch (e) {
    $('#sheetBody').textContent = '导入失败：' + e.message;
  }
}

/* ---------------------------------------------- 事件 */
let bookTitleTimer = null;

function bindBookEvents() {
  const bt = $('#bookTitle');
  if (bt) bt.oninput = () => {
    clearTimeout(bookTitleTimer);
    bookTitleTimer = setTimeout(async () => {
      if (!S.bookId) return;
      try {
        await api('PATCH', '/api/books/' + S.bookId, { title: bt.value.trim() || '未命名书稿' });
        if (BK.book) BK.book.book.title = bt.value.trim() || '未命名书稿';
        renderBookInspector();
      } catch (_) { }
    }, 700);
  };
  const ct = $('#chTitle');
  if (ct) ct.oninput = markDirty;
  const cx = $('#chText');
  if (cx) cx.oninput = markDirty;
  const bw = $('#btnBookWrite');
  if (bw) bw.onclick = () => bookWrite('continue');
  const bc = $('#btnBookCheck');
  if (bc) bc.onclick = bookCheck;
  const be = $('#btnBookExport');
  if (be) be.onclick = bookExportSheet;
  const bs = $('#btnChSnap');
  if (bs) bs.onclick = showSnapshots;
  const bo = $('#btnChOutline');
  if (bo) bo.onclick = openChapterOutline;
  const bm = $('#btnBookMenu');
  if (bm) bm.onclick = () => $('#panel').classList.toggle('open');
  const bL = $('#btnBookList');
  if (bL) bL.onclick = backToBooks;
  const sc = $('#btnSheetClose');
  if (sc) sc.onclick = closeSheet;
  const sm = $('#sheetMask');
  if (sm) sm.onclick = closeSheet;
  const scp = $('#btnSheetCopy');
  if (scp) scp.onclick = () => copyText($('#sheetBody').innerText);
  const fb = $('#fileBook');
  if (fb) fb.onchange = () => {
    const f = fb.files && fb.files[0];
    if (f) readBookFile(f);
    fb.value = '';
  };
  const vb = $('#viewBook');
  if (vb) {
    vb.addEventListener('dragover', e => { e.preventDefault(); });
    vb.addEventListener('drop', e => {
      e.preventDefault();
      const f = e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) readBookFile(f);
    });
  }
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSheet();
    if (S.view === 'book' && (e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      saveChapter();
    }
  });
}

boot();
