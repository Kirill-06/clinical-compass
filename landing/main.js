// Источник: evaluation/final_model_report.md (155 сообщений, 172 размеченных факта).
const METRICS = [
  { label: 'Находит сигналы риска', old: 0.368, next: 0.842 },
  { label: 'Полнота, всего', old: 0.721, next: 0.797 },
  { label: 'F1, всего', old: 0.656, next: 0.704 },
  { label: 'Точность, всего', old: 0.602, next: 0.631 },
  { label: 'F1 по препаратам', old: 0.718, next: 0.635 },
];
const DOMAIN = [0.3, 0.9];
const TICKS = [0.3, 0.5, 0.7, 0.9];

const fmt = (v) => v.toFixed(2).replace('.', ',');
const pct = (v) => `${((v - DOMAIN[0]) / (DOMAIN[1] - DOMAIN[0])) * 100}%`;

document.documentElement.classList.add('js');

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function point(kind, metric, value) {
  const btn = el('button', `db-pt db-pt--${kind}`);
  btn.type = 'button';
  btn.style.left = pct(value);
  btn.dataset.tip = `${metric.label}: ${kind === 'old' ? 'v1.1' : 'v1.2'} — ${fmt(value)}`;
  btn.setAttribute('aria-label', btn.dataset.tip);
  return btn;
}

function renderChart() {
  const root = document.getElementById('dumbbell');
  const tbody = document.querySelector('#chart-table tbody');
  if (!root || !tbody) return;

  for (const m of METRICS) {
    const row = el('div', 'db-row');
    row.append(el('div', 'db-label', m.label));

    const track = el('div', 'db-track');
    const lo = Math.min(m.old, m.next);
    const hi = Math.max(m.old, m.next);
    const bar = el('div', m.next < m.old ? 'db-bar db-bar--down' : 'db-bar');
    bar.style.left = pct(lo);
    bar.style.width = `calc(${pct(hi)} - ${pct(lo)})`;

    const oldVal = el('span', 'db-val', fmt(m.old));
    oldVal.style.left = pct(m.old);
    oldVal.style.top = 'auto';
    oldVal.style.bottom = '-4px';
    const newVal = el('span', 'db-val db-val--new', fmt(m.next));
    newVal.style.left = pct(m.next);

    track.append(bar, point('old', m, m.old), point('new', m, m.next), oldVal, newVal);
    row.append(track);
    root.append(row);

    const tr = el('tr');
    tr.append(el('th', '', m.label), el('td', '', fmt(m.old)), el('td', '', fmt(m.next)));
    tr.firstChild.scope = 'row';
    tbody.append(tr);
  }

  const axis = el('div', 'db-axis');
  axis.setAttribute('aria-hidden', 'true');
  const ticks = el('div', 'db-ticks');
  for (const t of TICKS) {
    const s = el('span', '', fmt(t).replace(/0$/, ''));
    s.style.left = pct(t);
    ticks.append(s);
  }
  axis.append(el('div'), ticks);
  root.append(axis);
}

function wireTooltip() {
  const chart = document.querySelector('.chart');
  const tip = document.getElementById('tooltip');
  if (!chart || !tip) return;

  const show = (target) => {
    const box = chart.getBoundingClientRect();
    const r = target.getBoundingClientRect();
    tip.textContent = target.dataset.tip;
    tip.style.left = `${r.left + r.width / 2 - box.left}px`;
    tip.style.top = `${r.top - box.top + 4}px`;
    tip.hidden = false;
  };
  const hide = () => { tip.hidden = true; };

  chart.addEventListener('pointerover', (e) => {
    const t = e.target.closest('.db-pt');
    if (t) show(t);
  });
  chart.addEventListener('pointerout', (e) => {
    if (e.target.closest('.db-pt')) hide();
  });
  chart.addEventListener('focusin', (e) => {
    const t = e.target.closest('.db-pt');
    if (t) show(t);
  });
  chart.addEventListener('focusout', hide);
}

function wireReveal() {
  const items = document.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    items.forEach((n) => n.classList.add('is-in'));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-in');
      io.unobserve(entry.target);
    }
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
  items.forEach((n, i) => {
    n.style.transitionDelay = `${(i % 5) * 70}ms`;
    io.observe(n);
  });
}

function wireHeader() {
  const header = document.querySelector('.top');
  if (!header) return;
  const sentinel = el('div');
  sentinel.style.cssText = 'position:absolute;top:8px;height:1px;width:1px';
  document.body.prepend(sentinel);
  new IntersectionObserver(([entry]) => {
    header.classList.toggle('is-scrolled', !entry.isIntersecting);
  }).observe(sentinel);
}

renderChart();
wireTooltip();
wireReveal();
wireHeader();
