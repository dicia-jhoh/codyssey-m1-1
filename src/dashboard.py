"""보너스 — 기간·기법을 바꿔 가며 탐색하는 단일 HTML 대시보드.

**미션 제약**상 서버를 띄우지 않습니다. 대신 데이터를 JSON 으로 페이지 안에 심고,
브라우저에서 자바스크립트가 **다시 그리는** 방식으로 만듭니다. 파일 하나만 열면
기간 슬라이더와 기법 선택이 그 자리에서 동작합니다.

차트를 이미지가 아니라 **인라인 SVG 로 직접 그리는** 이유: matplotlib PNG 를 심으면
기간을 바꿀 때마다 서버가 다시 그려야 합니다. SVG 를 자바스크립트로 그리면 브라우저
안에서 즉시 반응합니다 — 외부 라이브러리 없이 `<path>` 좌표만 계산하면 됩니다.
"""

from __future__ import annotations

import json
import os

TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>항공 승객 수 탐색 대시보드 (M1-1)</title>
<style>
  :root { --bg:#f6f7f9; --card:#fff; --text:#20222a; --muted:#6b7280; --line:#e4e6eb;
          --raw:#4C72B0; --trend:#C44E52; --accent:#55A868; }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--text);
         font-family:system-ui,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; line-height:1.6; }
  .wrap { max-width:1040px; margin:0 auto; }
  h1 { margin:0 0 4px; font-size:24px; }
  .sub { color:var(--muted); margin:0 0 20px; font-size:14px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          padding:18px; margin-bottom:16px; }
  .controls { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
  label { display:block; font-size:13px; color:var(--muted); margin-bottom:6px; }
  input[type=range] { width:100%; }
  .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px;
          margin-top:4px; }
  .kpi { background:var(--bg); border-radius:10px; padding:12px; }
  .kpi .label { font-size:12px; color:var(--muted); }
  .kpi .value { font-size:20px; font-weight:700; margin-top:2px; }
  .legend { font-size:13px; color:var(--muted); margin-top:8px; }
  .swatch { display:inline-block; width:12px; height:3px; vertical-align:middle;
            margin-right:4px; }
  table { width:100%; border-collapse:collapse; font-size:14px; }
  th,td { text-align:right; padding:7px 10px; border-bottom:1px solid var(--line); }
  th:first-child, td:first-child { text-align:left; }
  th { color:var(--muted); font-weight:600; }
  svg { width:100%; height:auto; display:block; }
  .hint { font-size:13px; color:var(--muted); margin-top:10px; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#15171c; --card:#1e2127; --text:#e9eaee; --muted:#99a0ac; --line:#2d3138; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>항공 승객 수 탐색 대시보드</h1>
  <p class="sub">기간과 기법을 바꿔 가며 살펴봅니다 · 데이터 __PERIOD__ · __POINTS__개월</p>

  <div class="card">
    <div class="controls">
      <div>
        <label>시작 <b id="fromLabel"></b></label>
        <input type="range" id="from" min="0" max="__MAX_INDEX__" value="0">
      </div>
      <div>
        <label>끝 <b id="toLabel"></b></label>
        <input type="range" id="to" min="0" max="__MAX_INDEX__" value="__MAX_INDEX__">
      </div>
      <div>
        <label>보기</label>
        <select id="mode">
          <option value="raw">원계열 + 이동평균</option>
          <option value="yoy">전년 동월 대비 변화율(%)</option>
          <option value="mom">전월 대비 변화율(%)</option>
        </select>
      </div>
      <div>
        <label>이동평균 창 <b id="windowLabel">12</b>개월</label>
        <input type="range" id="window" min="2" max="24" value="12">
      </div>
    </div>
    <div class="kpis" id="kpis"></div>
  </div>

  <div class="card">
    <svg id="chart" viewBox="0 0 900 360" role="img" aria-label="선택 구간 차트"></svg>
    <div class="legend" id="legend"></div>
    <p class="hint">슬라이더로 구간을 좁히면 그 구간만 다시 계산합니다 — 지표도 함께 바뀝니다.</p>
  </div>

  <div class="card">
    <h2 style="font-size:17px;margin:0 0 10px">선택 구간 연도별 통계</h2>
    <table id="yearTable">
      <thead><tr><th>연도</th><th>합계</th><th>평균</th><th>최대</th><th>CV%</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
</div>

<script>
const MONTHS = __MONTHS_JSON__;
const VALUES = __VALUES_JSON__;

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 1) => Number(n).toFixed(d);

/* 중심 이동평균 — 파이썬 쪽 analysis.moving_average 와 같은 방식(짝수 창은 양 끝 0.5 가중) */
function movingAverage(values, window) {
  const half = Math.floor(window / 2);
  const out = new Array(values.length).fill(null);
  for (let i = half; i < values.length - half; i++) {
    const chunk = values.slice(i - half, i + half + 1);
    let sum;
    if (window % 2 === 0) {
      sum = chunk.slice(1, -1).reduce((a, b) => a + b, 0) + (chunk[0] + chunk[chunk.length - 1]) / 2;
    } else {
      sum = chunk.reduce((a, b) => a + b, 0);
    }
    out[i] = sum / window;
  }
  return out;
}

function changeRate(values, lag) {
  const out = new Array(values.length).fill(null);
  for (let i = lag; i < values.length; i++) {
    if (values[i - lag]) out[i] = (values[i] - values[i - lag]) / values[i - lag] * 100;
  }
  return out;
}

function stdev(values) {
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1 || 1);
  return Math.sqrt(variance);
}

/* 선택 구간만 잘라 계산한다. 전체로 계산한 뒤 자르면 구간 끝의 이동평균이
   바깥 값까지 참조해, "이 구간만 봤을 때" 의 값과 달라진다. */
function slice() {
  let from = Number($('from').value);
  let to = Number($('to').value);
  if (from > to) [from, to] = [to, from];
  return { from, to, months: MONTHS.slice(from, to + 1), values: VALUES.slice(from, to + 1) };
}

function renderChart(months, series, extra, mode) {
  const W = 900, H = 360, PAD = { l: 54, r: 16, t: 16, b: 34 };
  const all = series.concat(extra || []).filter((v) => v !== null && !Number.isNaN(v));
  if (!all.length) { $('chart').innerHTML = ''; return; }
  let lo = Math.min(...all), hi = Math.max(...all);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;

  const x = (i) => PAD.l + i * (W - PAD.l - PAD.r) / Math.max(1, series.length - 1);
  const y = (v) => H - PAD.b - (v - lo) * (H - PAD.t - PAD.b) / (hi - lo);

  const path = (values) => {
    let d = '', pen = false;
    values.forEach((v, i) => {
      if (v === null || Number.isNaN(v)) { pen = false; return; }
      d += (pen ? 'L' : 'M') + fmt(x(i), 1) + ' ' + fmt(y(v), 1) + ' ';
      pen = true;
    });
    return d.trim();
  };

  /* y축 눈금 5개 — 값 범위를 균등 분할한다 */
  let ticks = '';
  for (let k = 0; k <= 4; k++) {
    const v = lo + (hi - lo) * k / 4;
    const py = y(v);
    ticks += `<line x1="${PAD.l}" y1="${py}" x2="${W - PAD.r}" y2="${py}"
                stroke="currentColor" stroke-opacity="0.12"/>
              <text x="${PAD.l - 8}" y="${py + 4}" text-anchor="end" font-size="11"
                fill="currentColor" opacity="0.65">${fmt(v, 0)}</text>`;
  }

  /* x축은 1월만 라벨 — 전부 찍으면 읽을 수 없다 */
  let xlabels = '';
  months.forEach((m, i) => {
    if (!m.endsWith('-01')) return;
    xlabels += `<text x="${x(i)}" y="${H - 10}" text-anchor="middle" font-size="11"
                  fill="currentColor" opacity="0.65">${m.slice(0, 4)}</text>`;
  });

  /* 변화율 모드에서는 0선을 그린다 — 증감을 가르는 기준이 없으면 부호를 눈으로 세야 한다 */
  const zero = (mode !== 'raw' && lo < 0 && hi > 0)
    ? `<line x1="${PAD.l}" y1="${y(0)}" x2="${W - PAD.r}" y2="${y(0)}"
         stroke="currentColor" stroke-opacity="0.5"/>` : '';

  const main = mode === 'raw' ? 'var(--raw)' : 'var(--accent)';
  const extraPath = extra
    ? `<path d="${path(extra)}" fill="none" stroke="var(--trend)" stroke-width="2.6"/>` : '';

  $('chart').innerHTML = ticks + zero + xlabels +
    `<path d="${path(series)}" fill="none" stroke="${main}" stroke-width="1.8"/>` + extraPath;
}

function render() {
  const { months, values } = slice();
  const mode = $('mode').value;
  const window = Number($('window').value);
  $('windowLabel').textContent = window;
  $('fromLabel').textContent = months[0] || '-';
  $('toLabel').textContent = months[months.length - 1] || '-';

  let series, extra = null, legend;
  if (mode === 'raw') {
    series = values;
    extra = movingAverage(values, window);
    legend = `<span class="swatch" style="background:var(--raw)"></span>월별 승객 수
              <span style="margin-left:14px"><span class="swatch"
              style="background:var(--trend)"></span>${window}개월 이동평균</span>`;
  } else {
    const lag = mode === 'yoy' ? 12 : 1;
    series = changeRate(values, lag);
    legend = `<span class="swatch" style="background:var(--accent)"></span>
              ${lag === 12 ? '전년 동월' : '전월'} 대비 변화율(%)`;
  }
  $('legend').innerHTML = legend;
  renderChart(months, series, extra, mode);

  /* KPI — 선택 구간만으로 다시 계산한다 */
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const yoy = changeRate(values, 12).filter((v) => v !== null);
  const avgYoy = yoy.length ? yoy.reduce((a, b) => a + b, 0) / yoy.length : null;
  const growth = values.length > 1 ? (values[values.length - 1] - values[0]) / values[0] * 100 : 0;
  $('kpis').innerHTML = [
    ['구간 길이', values.length + '개월'],
    ['평균', fmt(mean, 1)],
    ['최대 / 최소', `${Math.max(...values)} / ${Math.min(...values)}`],
    ['구간 성장', fmt(growth, 1) + '%'],
    ['평균 전년비', avgYoy === null ? '-' : fmt(avgYoy, 1) + '%'],
    ['변동계수', fmt(stdev(values) / mean * 100, 1) + '%'],
  ].map(([label, value]) =>
    `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div></div>`
  ).join('');

  /* 연도별 표 */
  const byYear = {};
  months.forEach((m, i) => {
    const year = m.slice(0, 4);
    (byYear[year] = byYear[year] || []).push(values[i]);
  });
  $('yearTable').querySelector('tbody').innerHTML = Object.keys(byYear).sort().map((year) => {
    const vals = byYear[year];
    const m = vals.reduce((a, b) => a + b, 0) / vals.length;
    const cv = vals.length > 1 ? stdev(vals) / m * 100 : 0;
    return `<tr><td>${year}</td><td>${fmt(vals.reduce((a, b) => a + b, 0), 0)}</td>
            <td>${fmt(m, 1)}</td><td>${Math.max(...vals)}</td><td>${fmt(cv, 1)}</td></tr>`;
  }).join('');
}

['from', 'to', 'mode', 'window'].forEach((id) => {
  $(id).addEventListener('input', render);
});
render();
</script>
</body>
</html>
"""


def build_html(series, summary: dict) -> str:
    """대시보드 HTML 문자열을 만든다. 데이터는 페이지 안에 JSON 으로 심는다.

    `str.format()` 을 쓰지 않고 치환하는 이유: 템플릿 안에 CSS 와 자바스크립트가 있고
    거기엔 중괄호가 가득하다. format 은 그것들을 전부 치환 대상으로 읽어 죽는다
    (실제로 겪었다). 이스케이프(`{{`)로 막을 수도 있지만 코드가 읽기 어려워진다.
    """
    replacements = {
        "__PERIOD__": summary["period"],
        "__POINTS__": str(len(series)),
        "__MAX_INDEX__": str(len(series) - 1),
        "__MONTHS_JSON__": json.dumps(series.months),
        "__VALUES_JSON__": json.dumps(series.values),
    }
    html_text = TEMPLATE
    for placeholder, value in replacements.items():
        html_text = html_text.replace(placeholder, value)
    return html_text


def save(html_text: str, out_dir: str = "output") -> str:
    """HTML 을 파일로 저장 → 경로."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "dashboard.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return path
