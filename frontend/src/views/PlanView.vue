<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchControllable, fetchForecast, fetchPlan, triggerPlanRefresh } from '../api.js'
import ControllableDeviceCard from '../components/ControllableDeviceCard.vue'
import PlotlyChart from '../components/PlotlyChart.js'
import { planning, planVersion } from '../composables/useStatus.js'
import { series, withAlpha } from '../lib/chartTheme'
import { deviceLink } from '../lib/deviceLinks'
import { fmtDateTime } from '../lib/format'
import { plotTime } from '../lib/plotTime'
import { PURPOSE_ORDER, PURPOSE_TITLES, purposeOf } from '../lib/purposes'

// The future: what the plan does over its horizon.  One chart of where the
// energy comes from and where it goes, the forecasts the plan is built on
// (consumption by what it is for, solar, prices), and the plan of each
// device Nornwatt runs.
/* eslint-disable @typescript-eslint/no-explicit-any */
const plan = ref<any | null>(null)
const forecast = ref<any | null>(null)
const controllable = ref<any[]>([])
const loaded = ref(false)
const refreshing = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

async function refresh() {
  try {
    const [p, f, c] = await Promise.all([fetchPlan(), fetchForecast(), fetchControllable()])
    plan.value = p
    forecast.value = f
    controllable.value = c?.devices ?? []
  } catch (e) {
    console.error('PlanView refresh failed', e)
  } finally {
    loaded.value = true
  }
}
async function triggerRefresh() {
  refreshing.value = true
  try { await triggerPlanRefresh() } catch (e) { console.error(e) }
  await refresh()
  refreshing.value = false
}
onMounted(() => { refresh(); timer = setInterval(refresh, 60_000) })
onUnmounted(() => clearInterval(timer))
// Refetch the moment the server publishes a new plan.
watch(planVersion, refresh)

const planMeta = computed(() => (plan.value?.created_at
  ? `Plan created: ${fmtDateTime(plan.value.created_at)} · step ${plan.value.step_minutes} min`
  : loaded.value ? 'No plan yet' : ''))

// X axis: hours, with a tick per 15-minute step.
const XAXIS = { type: 'date', tickformat: '%H', tickangle: 0, minor: { dtick: 900000, ticks: 'outside', ticklen: 4 } }
// The loads Nornwatt runs (heating, cooling): the same colour in both charts.
const LOADS = '#14a3b8'
const KW = '%{x|%a %H:%M}  %{y:.2f} kW<extra>%{fullData.name}</extra>'

const ts = computed<string[]>(() => forecast.value?.timestamps ?? [])
const x = computed(() => ts.value.map(plotTime))

/** Planned power per kind of device and step: what each kind takes (+) or gives (−). */
const flows = computed(() => {
  const n = ts.value.length
  const index = new Map(ts.value.map((t, i) => [t, i]))
  const zero = () => new Array<number>(n).fill(0)
  const out = { charge: zero(), discharge: zero(), cars: zero(), loads: zero() }
  const kind = new Map<string, string>(controllable.value.map(d => [d.charger_id ?? d.device_id, d.category]))
  for (const d of controllable.value) kind.set(d.device_id, d.category)
  for (const intent of plan.value?.intents ?? []) {
    const i = index.get(intent.timestep)
    const kw = intent.planned_kw ?? 0
    if (i == null || !kw) continue
    const category = kind.get(intent.device_id)
    if (category === 'vehicle' || category === 'charger') out.cars[i] += Math.max(kw, 0)
    else if (category === 'battery' || (category == null && intent.stored_energy_kwh != null)) {
      if (kw > 0) out.charge[i] += kw
      else out.discharge[i] -= kw
    } else out.loads[i] += Math.max(kw, 0)
  }
  return out
})

/** PV and grid as the plan was solved with (the forecast can be below the live production). */
const solved = computed(() => {
  const n = ts.value.length
  const index = new Map(ts.value.map((t, i) => [t, i]))
  const pv = [...(forecast.value?.pv_kw ?? [])] as number[]
  const imp = new Array<number | null>(n).fill(null)
  const exp = new Array<number | null>(n).fill(null)
  for (const f of plan.value?.flows ?? []) {
    const i = index.get(f.timestep)
    if (i == null) continue
    pv[i] = f.pv_kw
    imp[i] = f.grid_import_kw
    exp[i] = f.grid_export_kw
  }
  return { pv, imp, exp }
})

const has = (values: number[]) => values.some(v => v > 0.0005)

// The flow chart shows one bar per hour: the mean of the plan's steps in it.
// Eight series in 15-minute bars over two days are too dense to read; the
// steps themselves are on the cards of the devices below.
const hours = computed(() => {
  const starts: string[] = []
  const members: number[][] = []
  ts.value.forEach((t, i) => {
    const d = new Date(t)
    d.setMinutes(0, 0, 0)
    const key = d.toISOString()
    if (starts.at(-1) !== key) { starts.push(key); members.push([]) }
    members.at(-1)!.push(i)
  })
  return { x: starts.map(plotTime), members }
})
const perHour = (values: number[]) =>
  hours.value.members.map(m => m.reduce((a, i) => a + (values[i] ?? 0), 0) / m.length)

// ── where the energy comes from (above the line) and where it goes (below) ──
const flowTraces = computed(() => {
  if (!ts.value.length) return []
  const c = series()
  const f = flows.value
  const cons: number[] = forecast.value?.consumption_kw ?? []
  const { pv, imp, exp } = solved.value
  const gridImport = pv.map((p, i) => imp[i] ?? Math.max(0, (cons[i] ?? 0) + f.charge[i] + f.cars[i] + f.loads[i] - p - f.discharge[i]))
  const gridExport = pv.map((p, i) => exp[i] ?? Math.max(0, p + f.discharge[i] - (cons[i] ?? 0) - f.charge[i] - f.cars[i] - f.loads[i]))
  const bar = (name: string, y: number[], color: string) =>
    ({ name, type: 'bar', x: hours.value.x, y: perHour(y), marker: { color }, hovertemplate: KW })
  const down = (y: number[]) => y.map(v => -v)
  return [
    bar('Solar', pv, c.solar),
    bar('From the batteries', f.discharge, c.battery),
    bar('From the grid', gridImport, c.import),
    bar('House', down(cons), c.home),
    ...(has(f.loads) ? [bar('Planned loads', down(f.loads), LOADS)] : []),
    ...(has(f.cars) ? [bar('Cars', down(f.cars), c.car)] : []),
    bar('Into the batteries', down(f.charge), withAlpha(c.battery, 0.5)),
    ...(has(gridExport) ? [bar('To the grid', down(gridExport), c.export)] : []),
  ].map(t => ({ ...t, customdata: (t.y as number[]).map(Math.abs), hovertemplate: '%{x|%a %H} h  %{customdata:.2f} kW<extra>%{fullData.name}</extra>' }))
})
const flowLayout = computed(() => ({
  yaxis: { title: 'kW', zeroline: true },
  xaxis: { type: 'date', tickformat: '%H', tickangle: 0 }, bargap: 0.12,
  annotations: [
    { xref: 'paper', yref: 'paper', x: 0.005, y: 0.99, xanchor: 'left', yanchor: 'top', text: '↑ comes from', showarrow: false, font: { size: 10 } },
    { xref: 'paper', yref: 'paper', x: 0.005, y: 0.01, xanchor: 'left', yanchor: 'bottom', text: '↓ goes to', showarrow: false, font: { size: 10 } },
  ],
}))

// ── the forecasts the plan is built on ──
const SHADES = [0.75, 0.45, 0.28, 0.6]
const forecastTraces = computed(() => {
  if (!ts.value.length) return []
  const c = series()
  const f = flows.value
  const byDevice: any[] = forecast.value?.consumption_by_device ?? []
  const traces: Record<string, unknown>[] = []
  const area = (name: string, y: number[], color: string, hover?: string[]) => ({
    name, x: x.value, y, mode: 'lines', stackgroup: 'use', line: { width: 0.6, color, shape: 'hv' }, fillcolor: color,
    customdata: hover, hovertemplate: `%{x|%a %H:%M}  %{y:.2f} kW${hover ? '%{customdata}' : ''}<extra>${name}</extra>`,
  })
  if (byDevice.length) {
    // One area per purpose; the largest consumers of the step are named in the tooltip.
    const purposes = PURPOSE_ORDER.filter(p => byDevice.some(d => purposeOf(d) === p))
    purposes.forEach((p, k) => {
      const members = byDevice.filter(d => purposeOf(d) === p)
      const y = ts.value.map((_, i) => members.reduce((a, d) => a + (d.kw[i] ?? 0), 0))
      const hover = ts.value.map((_, i) => members
        .map(d => ({ label: d.label, kw: d.kw[i] ?? 0 }))
        .filter(d => d.kw >= 0.01).sort((a, b) => b.kw - a.kw).slice(0, 6)
        .map(d => `<br>${d.label} ${d.kw.toFixed(2)} kW`).join(''))
      traces.push(area(PURPOSE_TITLES[p] ?? p, y, withAlpha(c.home, SHADES[k % SHADES.length]), hover))
    })
  } else {
    traces.push(area('House', forecast.value?.consumption_kw ?? [], withAlpha(c.home, 0.6)))
  }
  if (has(f.loads)) traces.push(area('Planned loads', f.loads, LOADS))
  if (has(f.cars)) traces.push(area('Cars', f.cars, withAlpha(c.car, 0.6)))
  traces.push({
    name: 'Solar', x: x.value, y: solved.value.pv, mode: 'lines', line: { color: c.solar, width: 2.2, shape: 'hv' },
    hovertemplate: KW,
  })
  return traces
})

const priceTraces = computed(() => {
  const f = forecast.value
  if (!f || !ts.value.length) return []
  const c = series()
  // The variable prices where the tariff has them (15-minute steps), else the blended tariff prices.
  const prices: number[] = f.variable_prices?.length ? f.variable_prices : f.prices
  const estimated: boolean[] = f.variable_price_is_estimated ?? []
  const ct = (v: number | null | undefined) => (v == null ? null : v * 100)
  const hover = '%{x|%a %H:%M}  %{y:.1f} ct/kWh<extra>%{fullData.name}</extra>'
  return [
    { name: 'Import', mode: 'lines', x: x.value, y: prices.map((p, i) => (estimated[i] ? null : ct(p))),
      line: { color: c.import, shape: 'hv' }, connectgaps: false, hovertemplate: hover },
    { name: 'Import, estimated', mode: 'lines', x: x.value, y: prices.map((p, i) => (estimated[i] ? ct(p) : null)),
      line: { color: c.import, dash: 'dot', shape: 'hv' }, connectgaps: false, hovertemplate: hover,
      showlegend: estimated.some(Boolean) },
    { name: 'Export', mode: 'lines', x: x.value, y: (f.export_prices ?? []).map(ct),
      line: { color: c.export, shape: 'hv' }, hovertemplate: hover },
  ]
})

// ── the plan per device, by what the devices are for ──
const groups = computed(() => PURPOSE_ORDER
  .map(p => ({
    id: p, title: PURPOSE_TITLES[p],
    devices: controllable.value.filter(d => purposeOf(d) === p)
      .sort((a, b) => String(a.label ?? a.device_id).localeCompare(String(b.label ?? b.device_id))),
  }))
  .filter(g => g.devices.length))
</script>

<template>
  <div>
    <div class="view-toolbar">
      <p class="footnote" style="margin:0">{{ planMeta }}</p>
      <span class="ev-actions-spacer" />
      <button class="btn btn-neutral" :disabled="refreshing || planning" @click="triggerRefresh">
        {{ refreshing ? '…' : '↺ Refresh plan' }}
      </button>
    </div>

    <div class="full panel">
      <h2>Where the energy comes from and where it goes</h2>
      <p class="panel-hint">
        One bar per hour. Above the line: the sources (solar, batteries, grid). Below it: the uses (the house,
        the loads and cars Nornwatt runs, the batteries, the grid). Both sides are equally high. The 15-minute
        steps of each device are further down.
      </p>
      <PlotlyChart :traces="flowTraces" :layout="flowLayout" barmode="relative" height="320px" data-testid="plan-flow" />
    </div>

    <div class="row2-eq">
      <div class="panel">
        <h2>Expected consumption and solar</h2>
        <p class="panel-hint">
          What the plan is built on: the consumption forecast by what it is for, the loads and cars as planned on
          top, and the solar forecast. A device's own forecast is on its page.
        </p>
        <PlotlyChart :traces="forecastTraces" :layout="{ yaxis: { title: 'kW', rangemode: 'tozero' }, xaxis: XAXIS }" height="250px" data-testid="plan-forecast" />
      </div>
      <div class="panel">
        <h2>Electricity prices</h2>
        <p class="panel-hint">What a kilowatt-hour costs from the grid and what it earns when fed in.</p>
        <PlotlyChart :traces="priceTraces" :layout="{ yaxis: { title: 'ct/kWh' }, xaxis: XAXIS }" height="250px" />
      </div>
    </div>

    <div v-for="g in groups" :key="g.id" class="full panel" :data-testid="'plan-' + g.id">
      <h2>{{ g.title }}</h2>
      <div class="ctrl-list">
        <ControllableDeviceCard
          v-for="d in g.devices" :key="d.device_id" :device="d"
          :to="deviceLink({ device_id: d.vehicle_id ?? d.device_id, category: d.category })"
        />
      </div>
    </div>
    <div v-if="loaded && !groups.length" class="full panel">
      <p class="panel-hint" style="margin:0">Nornwatt runs no device yet, so there is nothing to plan per device.</p>
    </div>
  </div>
</template>
