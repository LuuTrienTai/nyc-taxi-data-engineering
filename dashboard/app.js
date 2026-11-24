'use strict';

const $ = (id) => document.getElementById(id);
const count = new Intl.NumberFormat('en-US');
const decimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const screen = {
  analytics: ['NYC TLC / Yellow Taxi', 'Taxi demand & revenue'],
  pipeline: ['Monthly batch / Data quality', 'Pipeline explorer'],
  gold: ['PostgreSQL / Star schema', 'Gold warehouse'],
};
const datasets = {
  fact_trip: 'One accepted trip per row, joined to pickup zone, drop-off zone, calendar and weather.',
  dim_date: 'Calendar attributes for every date in this month. ISO weekday 1 is Monday.',
  dim_zone: 'One row per TLC location ID. The same lookup serves pickup and drop-off.',
  dim_weather: 'One row per local New York hour. Observations shows the number of source readings.',
  agg_hourly_zone: 'Trips, revenue, fare and distance by pickup hour and pickup zone.',
  agg_daily_trips: 'Trips, revenue, average distance and average duration by local pickup date.',
  agg_zone_revenue: 'Trips, total charges and average base fare by pickup zone.',
};
const state = { catalog: null, stats: null, audit: null, view: 'analytics', stage: 'bronze',
  run: '', reason: '', after: 0, pages: [0], next: null, revision: 0 };

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function option(select, value, label) {
  const opt = el('option', label);
  opt.value = value;
  select.append(opt);
}

function fillTable(target, headings, rows, emptyMessage = 'No records match the current selection.') {
  if (!rows.length) {
    target.replaceChildren(el('p', emptyMessage, 'muted'));
    return;
  }
  const table = el('table');
  const header = table.createTHead().insertRow();
  for (const heading of headings) {
    const cell = el('th', heading);
    cell.scope = 'col';
    header.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const value of row) {
      const td = tr.insertCell();
      if (value instanceof Node) td.append(value);
      else td.textContent = value ?? '—';
    }
  }
  target.replaceChildren(table);
}

async function request(path, params = {}) {
  const query = new URLSearchParams(params);
  const res = await fetch('/api/' + path + '?' + query);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Unable to load data.');
  return data;
}

function showError(message) {
  $('error').textContent = message;
  $('error').hidden = !message;
}

function filters() {
  return { month: $('month').value, borough: $('borough').value, zone: $('zone').value,
    location_role: $('location-role').value, date_from: $('date-from').value,
    date_to: $('date-to').value, weather: $('weather').value, hour: $('hour').value };
}

function setZones(selected = '') {
  $('zone').replaceChildren();
  option($('zone'), '', 'All zones');
  for (const zone of state.catalog.zones) {
    if (!$('borough').value || $('borough').value === zone.borough) {
      option($('zone'), zone.location_id, zone.zone_name);
    }
  }
  $('zone').value = selected;
  if ($('zone').selectedIndex < 0) $('zone').value = '';
}

function readView() {
  const key = location.hash.slice(1);
  return Object.hasOwn(screen, key) ? key : 'analytics';
}

function lastDay(month) {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(Date.UTC(year, monthNumber, 0)).toISOString().slice(0, 10);
}

function setDateBounds() {
  const month = $('month').value;
  if (!month) return;
  const first = month + '-01';
  const last = lastDay(month);
  for (const input of [$('date-from'), $('date-to')]) {
    input.min = first;
    input.max = last;
  }
  $('date-from').value = first;
  $('date-to').value = last;
}

function currentMonth() {
  return state.catalog.months.find((item) => item.month === $('month').value);
}

async function load() {
  const revision = ++state.revision;
  const view = state.view;
  const month = currentMonth();
  state.stats = null;
  showError('');
  $('empty').hidden = Boolean(month);
  $('empty').textContent = 'Load a month with the pipeline, then refresh this page.';
  $('synthetic').hidden = month?.source_kind !== 'synthetic';
  $('loading').hidden = true;
  for (const key of Object.keys(screen)) $(key).hidden = true;
  if (!month) return;
  if (!month.has_gold && view !== 'pipeline') {
    $('empty').hidden = false;
    $('empty').textContent = 'This month has no committed Gold data. Check Pipeline explorer for run status.';
    return;
  }
  $('loading').hidden = false;
  try {
    if (view === 'analytics') {
      const data = await request('analytics', filters());
      if (revision !== state.revision) return;
      state.stats = data;
      $('distance').replaceChildren();
      renderAnalytics();
    } else if (view === 'pipeline') {
      const data = await request('pipeline', { month: month.month, run: state.run, reason: state.reason, after: state.after });
      if (revision !== state.revision) return;
      state.audit = data;
      renderPipeline();
    } else {
      const data = await request('gold', { month: month.month, table: $('dataset').value, after: state.pages.at(-1) });
      if (revision !== state.revision) return;
      renderGold(data);
    }
    $(view).hidden = false;
  } catch (error) {
    if (revision === state.revision) showError(error.message);
  } finally {
    if (revision === state.revision) $('loading').hidden = true;
  }
}

function navigate() {
  state.view = readView();
  const [label, heading] = screen[state.view];
  $('section-label').textContent = label;
  $('heading').textContent = heading;
  for (const key of Object.keys(screen)) {
    if (key === state.view) $('nav-' + key).setAttribute('aria-current', 'page');
    else $('nav-' + key).removeAttribute('aria-current');
  }
  if (state.catalog) load();
}

function renderAnalytics() {
  const sum = { trips: 0, revenue: 0, fares: 0, distance: 0 };
  const periods = new Map();
  for (const row of state.stats.hourly) {
    for (const field of Object.keys(sum)) sum[field] += Number(row[field]);
    const entry = periods.get(row.wet) || { hours: 0, trips: 0 };
    entry.hours += 1;
    entry.trips += row.trips;
    periods.set(row.wet, entry);
  }
  $('kpis').replaceChildren();
  for (const [title, value] of [
    ['Taxi trips', count.format(sum.trips)],
    ['Total charges', money.format(sum.revenue)],
    ['Average base fare', sum.trips ? money.format(sum.fares / sum.trips) : '—'],
    ['Average distance', sum.trips ? decimal.format(sum.distance / sum.trips) + ' mi' : '—'],
    ['Average duration', sum.trips ? decimal.format(sum.duration / sum.trips) + ' min' : '—'],
  ]) {
    const card = el('div', undefined, 'kpi');
    card.append(el('span', title), el('strong', value));
    $('kpis').append(card);
  }
  const weatherRows = state.stats.weather_groups.map((row) => [
    row.temperature_band, count.format(row.hours), decimal.format(row.trips_per_hour),
    decimal.format(row.average_precipitation) + ' mm',
  ]);
  fillTable($('weather-comparison'),
    ['Temperature', 'Hours', 'Trips / hour', 'Avg. precipitation'], weatherRows);
  renderChart();
  renderZones();
}

function renderChart() {
  if (!state.stats) return;
  const interval = $('interval').value;
  const metric = $('metric').value;
  const format = metric === 'revenue' ? money : count;
  $('chart-title').textContent = (interval === 'day' ? 'Daily ' : 'Hourly ') +
    (metric === 'revenue' ? 'pickup revenue' : 'pickup demand');
  const bins = new Map();
  const weekdayNames = ['Monday–Friday', 'Saturday–Sunday'];
  for (const row of state.stats.hourly) {
    const key = interval === 'day' ? row.hour_local.slice(0, 10)
      : interval === 'hour' ? row.hour_local.slice(11, 13) + ':00'
      : weekdayNames[row.iso_weekday >= 6 ? 1 : 0];
    bins.set(key, (bins.get(key) || 0) + Number(row[metric]));
  }
  const values = [...bins].sort(([a], [b]) => a.localeCompare(b));
  const max = Math.max(1, ...values.map(([, value]) => value));
  $('chart').replaceChildren();
  $('chart-detail').textContent = values.length ? 'Select a bar to inspect its value.' : 'No hours match the current selection.';
  for (const [i, [key, value]] of values.entries()) {
    const label = key + ' · ' + format.format(value);
    const bar = el('button', undefined, 'bar');
    bar.type = 'button';
    bar.title = label;
    bar.setAttribute('aria-label', label);
    bar.setAttribute('aria-pressed', 'false');
    bar.append(el('i'), el('span', values.length < 16 || i % 4 === 0 || i === values.length - 1
      ? (interval === 'day' ? key.slice(8) : interval === 'hour' ? key.slice(0, 2) : (i === 0 ? 'Weekdays' : 'Weekend')) : ''));
    bar.style.setProperty('--height', Math.max(value ? 3 : 1, value / max * 140) + 'px');
    bar.addEventListener('click', () => {
      $('chart').querySelector('[aria-pressed=true]')?.setAttribute('aria-pressed', 'false');
      bar.setAttribute('aria-pressed', 'true');
      $('chart-detail').textContent = label + (metric === 'trips' ? ' trips' : ' in total charges');
    });
    $('chart').append(bar);
  }
}

function renderZones() {
  if (!state.stats) return;
  const key = $('ranking').value;
  $('zone-heading').textContent = $('location-role').value === 'pickup' ? 'Pickup zones' : 'Drop-off zones';
  const rows = [...state.stats.zones].sort((a, b) => Number(b[key]) - Number(a[key])).slice(0, 12);
  fillTable($('zones'), [($('location-role').value === 'pickup' ? 'Pickup' : 'Drop-off') + ' zone', 'Trips', 'Charges', 'Avg. fare'], rows.map((row) => {
    const label = el('div');
    const button = el('button', row.zone_name, 'table-link');
    button.type = 'button';
    button.addEventListener('click', () => {
      $('borough').value = row.borough;
      setZones(String(row.location_id));
      load();
    });
    label.append(button, el('small', row.borough, 'subtle'));
    return [label, count.format(row.trips), money.format(row.revenue), money.format(row.average_fare)];
  }));
}

function preview(title, payload) {
  const details = el('details');
  details.append(el('summary', title), el('pre', JSON.stringify(payload, null, 2)));
  return details;
}

function renderPipeline() {
  const {runs, run} = state.audit;
  $('run').replaceChildren();
  for (const item of runs) option($('run'), item.run_id, '#' + item.run_id + ' · ' + item.status);
  $('run').value = run?.run_id ?? '';
  $('run').disabled = !runs.length;
  $('run-summary').textContent = run ? '#' + run.run_id + ' · ' + run.status +
    (run.finished_at ? ' · ' + new Date(run.finished_at).toLocaleString() : '') : 'Waiting for a run.';
  for (const [id, key] of [['bronze-count', 'rows_read'], ['silver-count', 'rows_loaded'],
    ['gold-count', 'rows_loaded'], ['rejected-count', 'rows_rejected']]) {
    $(id).textContent = run?.[key] == null ? '—' : count.format(run[key]);
  }
  renderStage();
}

function renderStage() {
  const {run, reasons, rejected, next} = state.audit;
  const target = $('stage-content');
  const titles = { bronze: 'Bronze files', silver: 'Silver processing in memory',
    gold: 'Gold load and reconciliation', quarantine: 'Rejected trips' };
  target.replaceChildren(el('h2', titles[state.stage]));
  for (const button of $('stages').querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.stage === state.stage));
  }
  if (!run?.bronze_files) {
    target.append(el('p', 'This run has no committed output. For a failed Airflow run, open the task log.', 'muted'));
    return;
  }
  if (run.status !== 'success' && ['silver', 'gold'].includes(state.stage)) {
    target.append(el('p', 'No trip passed validation. Existing Gold data is still available, if this month loaded successfully before.', 'muted'));
    return;
  }
  if (state.stage === 'bronze') {
    target.append(el('p', 'Source snapshot used by this run. File fingerprints identify the inputs used for replay.', 'muted'));
    const list = el('div', undefined, 'table-scroll');
    fillTable(list, ['Source', 'File', 'Rows', 'Size', 'SHA-256'], run.bronze_files.map((file) =>
      [file.source, file.file, file.rows == null ? '—' : count.format(file.rows),
        decimal.format(file.bytes / 1024) + ' KiB', preview('Show hash', file.sha256)]));
    target.append(list, el('h3', 'Sample input records'));
    for (const sample of run.preview) target.append(preview('Source row ' + sample.silver.source_row, sample.bronze));
  } else if (state.stage === 'silver') {
    target.append(el('p', 'Samples captured by the pipeline from accepted trips during this run.', 'muted'));
    const rules = el('ol');
    for (const rule of [
      'Check the input schema and validate timestamps, zone keys, distance and fares.',
      'Normalize timestamps and metrics, compute duration and calendar key, and align pickup hour to local weather.',
      'Generate the deterministic MD5 trip ID and route invalid and duplicate records to Quarantine.',
    ]) rules.append(el('li', rule));
    target.append(rules);
    for (const sample of run.preview) {
      const group = el('div', undefined, 'details-grid');
      group.append(preview('Bronze row ' + sample.silver.source_row, sample.bronze),
        preview('Silver row ' + sample.silver.source_row, sample.silver));
      target.append(group);
    }
  } else if (state.stage === 'gold') {
    target.append(el('p', count.format(run.rows_read) + ' Bronze rows = ' + count.format(run.rows_loaded) +
      ' committed fact rows + ' + count.format(run.rows_rejected) + ' rejected rows.', 'muted'));
    target.append(el('p', 'Trip counts and total charges reconciled across fact_trip and all three marts.', 'muted'));
    const tools = el('div', undefined, 'stage-tools');
    const link = el('a', 'Browse current Gold tables', 'table-link');
    link.href = '#gold';
    tools.append(link);
    target.append(tools);
  } else {
    target.append(el('p', 'One primary rejection reason per source row. Open a row to inspect the original record.', 'muted'));
    const label = el('label', 'Reason', 'stage-tools');
    const select = el('select');
    option(select, '', 'All reasons');
    for (const reason of reasons) option(select, reason.reason, reason.reason + ' · ' + count.format(reason.records));
    select.value = state.reason;
    select.addEventListener('change', () => {
      state.reason = select.value;
      state.after = 0;
      load();
    });
    label.append(select);
    target.append(label);
    for (const row of rejected) target.append(preview('Row ' + row.source_row + ' · ' + row.reason, row.raw_record));
    if (!rejected.length) target.append(el('p', 'No rejected rows in this selection.', 'muted'));
    const tools = el('div', undefined, 'stage-tools');
    for (const [labelText, value, disabled] of [['First page', 0, !state.after], ['Next page', next, next == null]]) {
      const button = el('button', labelText, 'quiet');
      button.disabled = disabled;
      button.addEventListener('click', () => { state.after = value; load(); });
      tools.append(button);
    }
    target.append(tools);
  }
}

function renderGold(data) {
  $('dataset-description').textContent = datasets[data.table];
  const keys = Object.keys(data.rows[0] || {});
  fillTable($('gold-data'), keys, data.rows.map((row) => keys.map((key) => row[key] == null ? '—' : String(row[key]))));
  state.next = data.next;
  $('gold-next').disabled = data.next === null;
  $('gold-back').disabled = state.pages.length < 2;
}

async function loadDistance() {
  const revision = state.revision;
  const button = $('distance-load');
  button.disabled = true;
  $('distance').replaceChildren(el('p', 'Calculating from trip records…', 'muted'));
  try {
    const rows = await request('distance', filters());
    if (revision !== state.revision) return;
    const labels = [
      'Under 1 mi', '1 to under 3 mi', '3 to under 5 mi',
      '5 to under 10 mi', '10 to under 20 mi', '20 mi and over',
    ];
    fillTable($('distance'), ['Distance band', 'Trips', 'Average base fare'],
      rows.map((row) => [labels[row.band - 1], count.format(row.trips), money.format(row.average_fare)]));
  } catch (error) {
    if (revision === state.revision) $('distance').replaceChildren(el('p', error.message, 'muted'));
  } finally {
    button.disabled = false;
  }
}

async function boot() {
  window.addEventListener('hashchange', navigate);
  navigate();
  $('loading').hidden = false;
  try {
    state.catalog = await request('catalog');
    $('month').replaceChildren();
    for (const month of state.catalog.months) option($('month'), month.month, month.month);
    $('month').value = (state.catalog.months.find((month) => month.has_gold) || state.catalog.months[0])?.month || '';
    if (!state.catalog.months.length) option($('month'), '', 'No runs');
    $('month').disabled = !state.catalog.months.length;
    for (const borough of new Set(state.catalog.zones.map((row) => row.borough))) option($('borough'), borough, borough);
    setDateBounds();
    setZones();
    for (let i = 0; i < 24; i++) option($('hour'), i, String(i).padStart(2, '0') + ':00');
    for (const table of Object.keys(datasets)) option($('dataset'), table, table);
    navigate();
  } catch (error) {
    showError(error.message);
  } finally {
    if (!state.catalog || !currentMonth()) $('loading').hidden = true;
  }
}


$('month').addEventListener('change', () => {
  setDateBounds();
  state.run = state.reason = '';
  state.after = 0;
  state.pages = [0];
  load();
});
$('borough').addEventListener('change', () => { setZones(); load(); });
for (const id of ['zone', 'weather', 'hour', 'location-role', 'date-from', 'date-to']) $(id).addEventListener('change', load);
$('reset').addEventListener('click', () => {
  $('borough').value = $('hour').value = '';
  $('date-from').value = $('month').value + '-01';
  $('date-to').value = lastDay($('month').value);
  $('location-role').value = 'pickup';
  $('weather').value = 'all';
  setZones();
  load();
});
for (const id of ['metric', 'interval']) $(id).addEventListener('change', renderChart);
$('ranking').addEventListener('change', renderZones);
$('distance-load').addEventListener('click', loadDistance);
$('run').addEventListener('change', () => {
  state.run = $('run').value;
  state.reason = '';
  state.after = 0;
  load();
});
$('stages').addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (button) {
    state.stage = button.dataset.stage;
    renderStage();
  }
});
$('dataset').addEventListener('change', () => { state.pages = [0]; load(); });
$('gold-next').addEventListener('click', () => { state.pages.push(state.next); load(); });
$('gold-back').addEventListener('click', () => { state.pages.pop(); load(); });
boot();
