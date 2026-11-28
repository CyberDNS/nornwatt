<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { fetchHistory, fetchSavingsSince } from '../api.js'
import { series } from '../lib/chartTheme'
import { fmt } from '../lib/format'
import { plotTime } from '../lib/plotTime'
import PlotlyChart from './PlotlyChart.js'
import RangeButtons from './RangeButtons.vue'

// The measured history of one device: power, and state of charge where the
// device has one.  Short ranges come in 5-minute steps, long ones per hour.
const props = defineProps<{
  deviceId: string
  /** Where the power is measured, when that is another device (a car's charger). */
  powerDeviceId?: string | null
  category?: string | null
  /** A device kept between two thresholds: the unit and the band of its
   *  value (temperature), drawn with the power. */
  value?: { unit?: string | null, bottom?: number | null, top?: number | null } | null
  /** The heading: "Measured" on a device's page, the device's name in a list of several. */
  title?: string
}>()

interface Row { t: string, power_w: number | null, soc_pct: number | null, pos_w: number | null, neg_w: number | null }
interface Range { label: string, hours: number, tickformat: string }

const RANGES: Range[] = [
  { label: '24 h', hours: 24, tickformat: '%H:%M' },
  { label: '3 d', hours: 72, tickformat: '%d.%m. %H:%M' },
  { label: '14 d', hours: 336, tickformat: '%d.%m.' },
  { label: '90 d', hours: 2160, tickformat: '%d.%m.' },
  { label: '1 y', hours: 8760, tickformat: '%b %y' },
]

const range = ref<Range>(RANGES[0])
const pending = ref<Range | null>(null)
const power = ref<Row[]>([])
const soc = ref<Row[]>([])
const bucketMinutes = ref(5)
/** The measured value of a threshold device (temperature) per 15 minutes. */
const values = ref<{ t: string, v: number }[]>([])
/** The rows are derived from Home Assistant, not measured by Nornwatt. */
const derived = ref(false)
// The value is kept with the savings slots, which reach a month back.
const VALUE_MAX_HOURS = 31 * 24
const loaded = ref(false)
let request = 0
let timer: ReturnType<typeof setInterval> | undefined

async function load(r: Range = range.value) {
  const mine = ++request
  pending.value = r
  const powerId = props.powerDeviceId ?? props.deviceId
  try {
    const resp = await fetchHistory(r.hours, [...new Set([props.deviceId, powerId])])
    if (mine !== request) return // a newer click won
    power.value = resp.measurements?.[powerId] ?? []
    soc.value = resp.measurements?.[props.deviceId] ?? []
    bucketMinutes.value = resp.bucket_minutes ?? 5
    derived.value = (resp.derived ?? []).includes(powerId)
    range.value = r
    values.value = props.value && r.hours <= VALUE_MAX_HOURS ? await loadValues(r.hours) : []
  } catch {
    /* keep what is shown */
  }
  if (mine === request) pending.value = null
  loaded.value = true
}
async function loadValues(hours: number): Promise<{ t: string, v: number }[]> {
  try {
    const resp = await fetchSavingsSince(new Date(Date.now() - hours * 3600_000))
    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    return (resp.slots ?? []).map((slot: any) => ({ t: slot.slot_start, v: slot.detail?.devices?.[props.deviceId]?.real_value }))
      .filter((p: { v: number | null | undefined }) => p.v != null)
  } catch {
    return []
  }
}
onMounted(() => { load(); timer = setInterval(() => load(), 5 * 60_000) })
onUnmounted(() => clearInterval(timer))
watch(() => [props.deviceId, props.powerDeviceId], () => load())

const hasPower = computed(() => power.value.some(r => r.power_w != null))
const hasSoc = computed(() => soc.value.some(r => r.soc_pct != null))

// Words for the two directions of energy, by what the device is.
const WORDS: Record<string, [string | null, string | null]> = {
  pv: [null, 'Produced'],
  battery: ['Charged', 'Discharged'],
  meter: ['Imported', 'Exported'],
  charger: ['Charged', null],
  vehicle: ['Charged', null],
}
const energy = computed(() => {
  const hours = bucketMinutes.value / 60
  const kwh = (key: 'pos_w' | 'neg_w') => power.value.reduce((a, r) => a + (r[key] ?? 0), 0) * hours / 1000
  const [into, out] = WORDS[props.category ?? ''] ?? ['Consumed', null]
  const parts: { label: string, kwh: number }[] = []
  if (into) parts.push({ label: into, kwh: kwh('pos_w') })
  if (out) parts.push({ label: out, kwh: kwh('neg_w') })
  return parts
})

const hasValue = computed(() => values.value.length > 0)
// Production counts down in the data (load convention); a PV system's page
// shows what it produced, upwards.
const sign = computed(() => (props.category === 'pv' ? -1 : 1))
const powerName = computed(() => (props.category === 'pv' ? 'Production' : 'Power'))

const traces = computed(() => {
  const out: Record<string, unknown>[] = []
  if (hasPower.value) {
    const rows = power.value.filter(r => r.power_w != null)
    out.push({
      name: powerName.value, mode: 'lines', x: rows.map(r => plotTime(r.t)),
      y: rows.map(r => sign.value * (r.power_w as number) / 1000),
      line: { width: 1.6, color: '#2a78d6', shape: 'hv' }, fill: 'tozeroy', fillcolor: 'rgba(42,120,214,.14)',
      hovertemplate: `%{x|%d.%m. %H:%M}  %{y:.2f} kW<extra>${powerName.value}</extra>`,
    })
  }
  if (hasValue.value) {
    const unit = props.value?.unit ?? ''
    out.push({
      name: unit === '°C' ? 'Temperature' : 'Value', mode: 'lines',
      x: values.value.map(p => plotTime(p.t)), y: values.value.map(p => p.v),
      yaxis: hasPower.value ? 'y2' : 'y', line: { width: 2, color: series().home },
      hovertemplate: `%{x|%d.%m. %H:%M}  %{y:.2f} ${unit}<extra></extra>`,
    })
  }
  if (hasSoc.value) {
    const rows = soc.value.filter(r => r.soc_pct != null)
    out.push({
      name: 'State of charge', mode: 'lines', x: rows.map(r => plotTime(r.t)), y: rows.map(r => r.soc_pct),
      yaxis: hasPower.value ? 'y2' : 'y', line: { width: 2, color: '#6250d6' },
      hovertemplate: '%{x|%d.%m. %H:%M}  %{y:.0f} %<extra>State of charge</extra>',
    })
  }
  return out
})

const layout = computed(() => {
  const second = hasValue.value
    ? { title: props.value?.unit || 'value' }
    : { title: '%', range: [0, 105] }
  const two = hasPower.value && (hasSoc.value || hasValue.value)
  // The band the value is kept in.
  const band = hasValue.value
    ? [props.value?.bottom, props.value?.top].filter((y): y is number => y != null).map(y => ({
        type: 'line', xref: 'paper', x0: 0, x1: 1, yref: two ? 'y2' : 'y', y0: y, y1: y,
        line: { color: series().import, width: 1, dash: 'dot' },
      }))
    : []
  return {
    xaxis: { type: 'date', tickformat: range.value.tickformat },
    yaxis: hasPower.value ? { title: 'kW', zeroline: true, rangemode: 'tozero' } : second,
    ...(two
      ? { yaxis2: { ...second, overlaying: 'y', side: 'right', showgrid: false }, margin: { t: 10, r: 45, b: 60, l: 50 } }
      : {}),
    shapes: band,
    showlegend: two,
  }
})
</script>

<template>
  <div class="full panel" data-testid="device-history">
    <div class="panel-head">
      <h3>{{ title ?? 'Measured' }}</h3>
      <span v-for="e in energy" v-show="hasPower" :key="e.label" class="link-row-sub">
        {{ e.label }} <b class="text-foreground tabular-nums">{{ fmt(e.kwh, e.kwh < 10 ? 2 : 1) }} kWh</b>
      </span>
      <span class="ev-actions-spacer" />
      <RangeButtons :ranges="RANGES" :active="pending ?? range" @pick="load" />
    </div>
    <PlotlyChart v-if="traces.length" :traces="traces" :layout="layout" height="280px" />
    <p v-else class="text-muted-foreground py-6 text-sm">
      {{ loaded ? 'Nothing recorded in this range yet.' : 'Loading…' }}
    </p>
    <p v-if="derived" class="panel-hint" data-testid="history-derived">
      This consumer has no meter of its own. Shown is what is left of the measured consumption after the
      consumers with their own meter, per hour, from Home Assistant.
    </p>
    <p v-if="value && range.hours > VALUE_MAX_HOURS" class="panel-hint">
      The {{ value.unit === '°C' ? 'temperature' : 'value' }} is kept for a month; longer ranges show the power only.
    </p>
    <p class="chart-hint">
      {{ derived ? 'Hourly values' : bucketMinutes === 5 ? '5-minute averages' : 'Hourly averages' }}. Drag to move in time, pinch or
      Ctrl + scroll to zoom, double-click to see everything.
    </p>
  </div>
</template>
