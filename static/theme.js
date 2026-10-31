/* ============================================================
   砚 Inkstone — 主题系统
   每套主题 = 一组 CSS 变量 + 背景 + 面板透明度档位
   ============================================================ */

const THEMES = [
  {
    id: 'paper', name: '宣纸', tag: '暖白 · 衬线',
    bg: 'radial-gradient(120% 90% at 12% 0%, #FBF9F4 0%, #F6F2E9 45%, #F1ECE0 100%)',
    surfaceAlphas: [0.50, 0.75, 0.92],
    vars: {
      '--paper': '#FAF8F3', '--paper-2': '#F4F0E7', '--paper-3': '#EDE8DC',
      '--ink': '#1C1B18', '--ink-2': '#35322C', '--ink-3': '#55504A',
      '--muted': '#837C6F', '--muted-2': '#A29B8D',
      '--line': '#E5DFD3', '--line-soft': '#EFEAE0',
      '--accent': '#B23A2F', '--accent-ink': '#8C2B23', '--accent-soft': '#F7EAE6',
      '--seal': '#B23A2F', '--radius': '12px',
    },
  },
  {
    id: 'sakura', name: '樱花', tag: '浪漫 · 插画',
    bg: 'linear-gradient(155deg, #FDF4F6 0%, #F9E7EE 45%, #EFE3F2 100%)',
    image: '/static/assets/bg-washi.jpg',
    surfaceAlphas: [0.58, 0.80, 0.94],
    vars: {
      '--paper': '#FCF7F7', '--paper-2': '#F7ECEF', '--paper-3': '#F0E1E7',
      '--ink': '#3B2B31', '--ink-2': '#4E3A41', '--ink-3': '#6B565D',
      '--muted': '#8E757D', '--muted-2': '#B09AA1',
      '--line': '#EEDCE2', '--line-soft': '#F6E8EC',
      '--accent': '#C2607A', '--accent-ink': '#9E4460', '--accent-soft': '#FBE9EF',
      '--seal': '#C2607A', '--radius': '14px',
    },
  },
  {
    id: 'pixel', name: '像素糖果', tag: '薄荷 · 硬边',
    bg: 'linear-gradient(180deg, #FBF6E9 0%, #F2ECDA 100%)',
    surfaceAlphas: [0.62, 0.86, 0.97],
    vars: {
      '--paper': '#FCF8EC', '--paper-2': '#F5EFDF', '--paper-3': '#EDE6D2',
      '--ink': '#2A2A33', '--ink-2': '#3C3C48', '--ink-3': '#5A5A68',
      '--muted': '#7C7C8A', '--muted-2': '#A5A5B0',
      '--line': '#D9D2BF', '--line-soft': '#EAE4D4',
      '--accent': '#5E9C7B', '--accent-ink': '#3F7A5B', '--accent-soft': '#E4F1E9',
      '--seal': '#5E9C7B', '--radius': '4px',
    },
  },
  {
    id: 'trainer', name: '复古掌机', tag: '红白 · 像素',
    bg: 'linear-gradient(180deg, #F7EFDC 0%, #EFE3C8 100%)',
    surfaceAlphas: [0.55, 0.80, 0.95],
    vars: {
      '--paper': '#FBF3DF', '--paper-2': '#F4E9CE', '--paper-3': '#EBDFC4',
      '--ink': '#2E2622', '--ink-2': '#463A33', '--ink-3': '#63534A',
      '--muted': '#8A7668', '--muted-2': '#AC9A8B',
      '--line': '#DCCBB0', '--line-soft': '#EBDFC9',
      '--accent': '#C0392B', '--accent-ink': '#96291D', '--accent-soft': '#F7E3DE',
      '--seal': '#C0392B', '--radius': '2px',
    },
  },
  {
    id: 'midnight', name: '午夜', tag: '深色 · 暖金',
    bg: 'radial-gradient(120% 90% at 20% 0%, #201F1C 0%, #171614 60%, #121110 100%)',
    surfaceAlphas: [0.05, 0.09, 0.14],
    dark: true,
    vars: {
      '--paper': '#1B1A17', '--paper-2': '#22211D', '--paper-3': '#2A2823',
      '--ink': '#EDE7DA', '--ink-2': '#D6CFC0', '--ink-3': '#B5AE9F',
      '--muted': '#8E8778', '--muted-2': '#6E685C',
      '--line': '#34322C', '--line-soft': '#2A2823',
      '--accent': '#D9A05B', '--accent-ink': '#EBB77A', '--accent-soft': '#3A2E20',
      '--seal': '#C0392B', '--radius': '12px',
    },
  },
  {
    id: 'forest', name: '森林', tag: '苔绿 · 安静',
    bg: 'radial-gradient(120% 90% at 10% 0%, #F4F7F1 0%, #E9F0E6 50%, #DDE7D9 100%)',
    surfaceAlphas: [0.50, 0.75, 0.92],
    vars: {
      '--paper': '#F7FAF4', '--paper-2': '#EDF3E9', '--paper-3': '#E2EBDD',
      '--ink': '#20281F', '--ink-2': '#33402F', '--ink-3': '#4C5B47',
      '--muted': '#6F7C69', '--muted-2': '#9AA694',
      '--line': '#D8E2D2', '--line-soft': '#E7EEE2',
      '--accent': '#4E7A52', '--accent-ink': '#3A5F3E', '--accent-soft': '#E3EFE4',
      '--seal': '#4E7A52', '--radius': '12px',
    },
  },
  {
    id: 'ocean', name: '海洋', tag: '雾蓝 · 清冷',
    bg: 'radial-gradient(120% 90% at 80% 0%, #F2F7F9 0%, #E4EFF4 50%, #D8E7EF 100%)',
    surfaceAlphas: [0.50, 0.75, 0.92],
    vars: {
      '--paper': '#F6FAFC', '--paper-2': '#EAF2F6', '--paper-3': '#DEEAF1',
      '--ink': '#1B262C', '--ink-2': '#2E3D45', '--ink-3': '#475A64',
      '--muted': '#6C7F89', '--muted-2': '#97A8B1',
      '--line': '#D3E1E8', '--line-soft': '#E4EEF3',
      '--accent': '#3E6E8E', '--accent-ink': '#2C5673', '--accent-soft': '#E0EDF4',
      '--seal': '#3E6E8E', '--radius': '12px',
    },
  },
  {
    id: 'sepia', name: '棕褐', tag: '旧书 · 昏黄',
    bg: 'radial-gradient(120% 90% at 15% 0%, #F7EEDC 0%, #F0E2C8 50%, #E7D5B7 100%)',
    surfaceAlphas: [0.52, 0.76, 0.93],
    vars: {
      '--paper': '#F8F1E1', '--paper-2': '#F1E6CF', '--paper-3': '#E8DABF',
      '--ink': '#382C1D', '--ink-2': '#4C3C28', '--ink-3': '#67523A',
      '--muted': '#8A7358', '--muted-2': '#AC9578',
      '--line': '#E0D0B4', '--line-soft': '#EEE1C9',
      '--accent': '#8A5A2B', '--accent-ink': '#6B431E', '--accent-soft': '#F1E4CF',
      '--seal': '#8A5A2B', '--radius': '12px',
    },
  },
];

const ACCENT_PRESETS = [
  '#B23A2F', '#C2607A', '#5E9C7B', '#3E6E8E',
  '#8A5A2B', '#7A5C9E', '#C0392B', '#2E7D6F',
];

function themeById(id) {
  return THEMES.find(t => t.id === id) || THEMES[0];
}

function tHex2rgb(h) {
  h = String(h).replace('#', '');
  if (h.length === 3) h = h.split('').map(c => c + c).join('');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function tShade(hex, p) {
  const [r, g, b] = tHex2rgb(hex);
  const f = x => Math.max(0, Math.min(255, Math.round(x * (1 + p))));
  return '#' + [f(r), f(g), f(b)].map(x => x.toString(16).padStart(2, '0')).join('');
}
function tMix(hex, to, p) {
  const a = tHex2rgb(hex), b = tHex2rgb(to);
  const f = (x, i) => Math.round(x * (1 - p) + b[i] * p);
  return '#' + [0, 1, 2].map(i => f(a[i], i).toString(16).padStart(2, '0')).join('');
}

/* app: { theme, accent, radius, fontSize, panelOpacity, backgroundId, intensity, blur, dim } */
function applyTheme(app, bgUrl) {
  const a = app || {};
  const t = themeById(a.theme);
  const root = document.documentElement;

  Object.keys(t.vars).forEach(k => root.style.setProperty(k, t.vars[k]));

  // 面板透明度：以主题档位为基准整体缩放
  const scale = a.panelOpacity == null ? 1 : a.panelOpacity;
  const clamp = x => Math.min(0.99, Math.max(0.03, x * scale));
  const [s1, s2, s3] = t.surfaceAlphas;
  root.style.setProperty('--surface-1', 'rgba(255,255,255,' + clamp(s1).toFixed(3) + ')');
  root.style.setProperty('--surface-2', 'rgba(255,255,255,' + clamp(s2).toFixed(3) + ')');
  root.style.setProperty('--surface-3', 'rgba(255,255,255,' + clamp(s3).toFixed(3) + ')');
  root.style.setProperty('--surface-solid', t.dark
    ? 'rgba(255,255,255,' + clamp(0.16).toFixed(3) + ')'
    : 'rgba(255,255,255,' + clamp(0.98).toFixed(3) + ')');

  // 强调色：主题自带，可被用户覆盖
  const accent = a.accent || t.vars['--accent'];
  root.style.setProperty('--accent', accent);
  root.style.setProperty('--accent-ink', tShade(accent, t.dark ? 0.35 : -0.24));
  root.style.setProperty('--accent-soft', tMix(accent, t.dark ? '#1B1A17' : '#FFFFFF', t.dark ? 0.82 : 0.9));

  if (a.radius != null) root.style.setProperty('--radius', a.radius + 'px');
  root.style.setProperty('--reader-size', (a.fontSize || 17) + 'px');

  document.body.dataset.theme = t.id;
  document.body.classList.toggle('is-dark', !!t.dark);

  const layer = document.getElementById('bgLayer');
  const pic = bgUrl || t.image || null;
  if (layer) {
    if (pic) {
      // 用 <img> 承载，CSS background 在部分 WebView2 里不绘制
      layer.innerHTML = '<img alt="" src="' + pic + '">';
      layer.style.backgroundImage = 'none';
      document.body.classList.add('has-image');
    } else {
      layer.innerHTML = '';
      layer.style.backgroundImage = t.bg;
      document.body.classList.remove('has-image');
    }
  }
  root.style.setProperty('--bg-intensity', bgUrl ? (a.intensity ?? 0.6) : 1);
  root.style.setProperty('--bg-blur', (a.blur || 0) + 'px');
  root.style.setProperty('--bg-dim', (a.dim ?? (bgUrl ? 0.12 : (t.image ? 0.13 : (t.dark ? 0.35 : 0.12)))));

  applyDecor(t.id, !!bgUrl);
}

/* ---------------- 主题专属装饰 ---------------- */

const PIXEL_SKY =
  '<svg width="420" height="200" viewBox="0 0 420 200" style="top:62px;right:16px" shape-rendering="crispEdges">' +
  '<g fill="#C6DCF5"><rect x="6" y="18" width="48" height="18"/><rect x="18" y="6" width="27" height="12"/><rect x="0" y="27" width="60" height="12"/></g>' +
  '<g fill="#E7D8F5"><rect x="96" y="40" width="42" height="15"/><rect x="108" y="30" width="24" height="10"/><rect x="90" y="48" width="54" height="10"/></g>' +
  '<g fill="#F8DCE7"><rect x="228" y="14" width="45" height="16"/><rect x="240" y="4" width="24" height="10"/><rect x="222" y="22" width="57" height="10"/></g>' +
  '<g fill="#D7E8F7"><rect x="330" y="58" width="38" height="13"/><rect x="340" y="49" width="20" height="9"/><rect x="324" y="65" width="48" height="8"/></g>' +
  '<g fill="#F3E3A8"><rect x="150" y="86" width="6" height="6"/><rect x="153" y="80" width="0" height="0"/></g>' +
  '<g fill="#E9C9D8"><rect x="60" y="104" width="5" height="5"/><rect x="300" y="96" width="5" height="5"/><rect x="386" y="130" width="5" height="5"/></g>' +
  '</svg>';

function applyDecor(id, hasImage) {
  document.querySelectorAll('.decor').forEach(n => n.remove());
  document.body.classList.remove('decor-on');

  if (id === 'pixel' && !hasImage) {
    const wrap = document.querySelector('.composer-wrap');
    if (!wrap) return;
    const d = document.createElement('div');
    d.className = 'decor decor-pixel';
    d.setAttribute('aria-hidden', 'true');
    d.innerHTML = '<img class="mascot dog" src="/static/assets/dog.png" alt="">' +
      '<img class="mascot cat" src="/static/assets/cat.png" alt="">';
    wrap.appendChild(d);
    document.body.classList.add('decor-on');
  }

  if (id === 'pixel' && !hasImage) {
    const d = document.createElement('div');
    d.className = 'decor decor-pixel-sky';
    d.setAttribute('aria-hidden', 'true');
    d.innerHTML = PIXEL_SKY;
    document.body.appendChild(d);
  }

  if (id === 'trainer' && !hasImage) {
    const wrap = document.querySelector('.composer-wrap');
    if (wrap) {
      const d = document.createElement('div');
      d.className = 'decor decor-dragon';
      d.setAttribute('aria-hidden', 'true');
      d.innerHTML = '<img src="/static/assets/dragon.png" alt="">';
      wrap.appendChild(d);
    }
  }

  if (id === 'sakura') {
    const d = document.createElement('div');
    d.className = 'decor decor-petals';
    d.setAttribute('aria-hidden', 'true');
    let html = '';
    for (let i = 0; i < 18; i++) html += '<i style="--i:' + i + '"></i>';
    d.innerHTML = html;
    document.body.appendChild(d);
    document.body.classList.add('decor-on');
  }
}
