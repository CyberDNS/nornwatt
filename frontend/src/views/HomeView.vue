<script setup lang="ts">
import type { Ref } from 'vue'
import type { Status } from '../composables/usePowerFlow'
import { Check, ChevronRight } from '@lucide/vue'
import { computed, inject, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import EnergyFlow from '../components/EnergyFlow.vue'
import ObservingBanner from '../components/ObservingBanner.vue'
import PowerChargeStatus from '../components/PowerChargeStatus.vue'
import PlotlyChart from '../components/PlotlyChart.js'
import { series, withAlpha } from '../lib/chartTheme'
import { useCars } from '../composables/useCars'
import { usePowerFlow } from '../composables/usePowerFlow'
import { useToday } from '../composables/useToday'
import { useLiveDevices } from '../composables/useLiveDevices'
import { deviceLink } from '../lib/deviceLinks'
import { fmt, fmtDevicePower, fmtEur, fmtPower, fmtPrice, fmtWhen, gainClass } from '../lib/format'
import { PURPOSE_ICONS, purposeOf } from '../lib/purposes'
import { plotTime, startOfToday } from '../lib/plotTime'

// Home: the house at a glance.  What flows where right now, today as one
// timeline (measured so far, planned ahead), what the plan does next, today's
// figures and the cars.  Every device has its own page under Devices.
const status = inject('status') as Ref<Status | null>
const { tiles, batterySocPct } = usePowerFlow(status)
const { measured, planned, prices, energy, savings, selfSufficiency, controllable, loaded } = useToday(status)
const { cars, chargers } = useCars()

// ── "now", for the marker in the charts ──
const now = ref(new Date())
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { timer = setInterval(() => { now.value = new Date() }, 60_000) })
onUnmounted(() => clearInterval(timer))
const nowMarker = computed(() => {
  const x = plotTime(now.value.toISOString())
  return {
    shapes: [{ type: 'line', xref: 'x', yref: 'paper', x0: x, x1: x, y0: 0, y1: 1, line: { color: series().neutral, width: 1.5, dash: 'dot' } }],
    annotations: [{ x, xref: 'x', yref: 'paper', y: 1.02, yanchor: 'bottom', text: 'now', showarrow: false, font: { size: 10 } }],
  }
})

// ── today: measured so far (solid) and planned ahead (dashed) ──
const todayTraces = computed(() => {
  const c = series()
  const C = { solar: c.solar, home: c.home, soc: c.battery }
  const nowMs = now.value.getTime()
  const past = measured.value
  const ahead = planned.value.filter(p => new Date(p.t).getTime() >= nowMs - 15 * 60_000)
  if (!past.length && !ahead.length) return []
  const x = (rows: typeof past) => rows.map(p => plotTime(p.t))
  const line = (name: string, rows: typeof past, key: 'solarKw' | 'homeKw', color: string, future: boolean, fill = false) => ({
    name: future ? `${name}, expected` : name, mode: 'lines', x: x(rows), y: rows.map(p => p[key]),
    line: { color, width: future ? 1.6 : 2, dash: future ? 'dot' : 'solid', shape: 'hv' },
    ...(fill ? { fill: 'tozeroy', fillcolor: withAlpha(color, future ? 0.1 : 0.25) } : {}),
    legendgroup: name, showlegend: !future,
    hovertemplate: `%{x|%H:%M}  %{y:.2f} kW<extra>${future ? `${name}, expected` : name}</extra>`,
  })
  const soc = (rows: typeof past, future: boolean) => {
    const r = rows.filter(p => p.socPct != null)
    return {
      name: future ? 'Battery, planned' : 'Battery', mode: 'lines', x: x(r), y: r.map(p => p.socPct), yaxis: 'y2',
      line: { color: C.soc, width: future ? 1.6 : 2.2, dash: future ? 'dot' : 'solid' },
      legendgroup: 'Battery', showlegend: !future,
      hovertemplate: `%{x|%H:%M}  %{y:.0f} %<extra>${future ? 'Battery, planned' : 'Battery'}</extra>`,
    }
  }
  const hasSoc = [...past, ...ahead].some(p => p.socPct != null)
  return [
    line('Solar', past, 'solarKw', C.solar, false, true),
    line('Solar', ahead, 'solarKw', C.solar, true, true),
    line('Home', past, 'homeKw', C.home, false),
    line('Home', ahead, 'homeKw', C.home, true),
    ...(hasSoc ? [soc(past, false), soc(ahead, true)] : []),
  ]
})
const todayLayout = computed(() => {
  const start = startOfToday()
  const end = new Date(start.getTime() + 24 * 3600_000)
  return {
    xaxis: { type: 'date', tickformat: '%H', range: [plotTime(start.toISOString()), plotTime(end.toISOString())] },
    yaxis: { title: 'kW', rangemode: 'tozero' },
    yaxis2: { title: 'Battery %', overlaying: 'y', side: 'right', range: [0, 105], showgrid: false },
    margin: { t: 22, r: 48, b: 60, l: 50 },
    ...nowMarker.value,
  }
})

// ── prices ahead ──
const priceTraces = computed(() => {
  if (!prices.value.length) return []
  const color = series().import
  const x = prices.value.map(p => plotTime(p.t))
  const y = (estimated: boolean) => prices.value.map(p => (p.estimated === estimated ? p.price * 100 : null))
  return [
    { name: 'Import price', mode: 'lines', x, y: y(false), line: { color, width: 2, shape: 'hv' }, connectgaps: false,
      hovertemplate: '%{x|%a %H:%M}  %{y:.1f} ct/kWh<extra></extra>' },
    { name: 'Estimated', mode: 'lines', x, y: y(true), line: { color, width: 1.6, dash: 'dot', shape: 'hv' }, connectgaps: false,
      hovertemplate: '%{x|%a %H:%M}  %{y:.1f} ct/kWh<extra>estimated</extra>' },
  ]
})
const priceRange = computed(() => {
  const real = prices.value.filter(p => !p.estimated)
  const list = real.length ? real : prices.value
  if (!list.length) return null
  const lo = list.reduce((a, p) => (p.price < a.price ? p : a))
  const hi = list.reduce((a, p) => (p.price > a.price ? p : a))
  return { lo: `${fmtPrice(lo.price)} ${fmtWhen(lo.t)}`, hi: `${fmtPrice(hi.price)} ${fmtWhen(hi.t)}` }
})

// ── what the plan does next ──
const MODE: Record<string, string> = {
  run: 'running', charge_from_grid: 'charging from the grid', charge_from_pv: 'charging from solar',
  charge_phase2: 'charging', force_charging: 'charging at full power', discharge: 'discharging',
  grid_feed_in: 'feeding into the grid', idle: 'idle', standby: 'idle',
}
const mode = (m: string | undefined) => MODE[m ?? ''] ?? (m ?? 'unknown').replace(/_/g, ' ')
const next = computed(() => controllable.value
  .filter(d => d.plan?.next_change)
  .map((d) => {
    const minutes: number = d.plan.next_change.in_minutes
    // With the day when that is not today: the plan reaches two days ahead.
    const at = fmtWhen(new Date(Date.now() + minutes * 60_000))
    return {
      id: d.device_id, label: d.label, minutes, at,
      now: mode(d.plan.current_mode), then: mode(d.plan.next_change.mode),
      inText: minutes < 60 ? `in ${Math.round(minutes)} min` : `in ${fmt(minutes / 60, 1)} h`,
      to: deviceLink({ device_id: d.device_id, category: d.category }),
    }
  })
  .sort((a, b) => a.minutes - b.minutes)
  .slice(0, 6))

// ── nothing configured yet: the first steps instead of empty charts ──
const configuration = computed(() => status.value?.configuration)
const firstStart = computed(() => configuration.value?.state === 'running' && configuration.value.devices === 0)
const homeAssistant = computed(() => configuration.value?.homeassistant ?? null)

const eur = fmtEur

// ── the devices by what they are for, each group at a glance ──
const live = useLiveDevices(status, { primary: true })
const MODE_NOW: Record<string, string> = { ...MODE, idle: 'idle', standby: 'idle', no_plan: 'idle' }
const modeNow = (d: { sp?: Record<string, unknown> }) => {
  const m = d.sp?.mode ? String(d.sp.mode) : ''
  return m ? (MODE_NOW[m] ?? m.replace(/_/g, ' ')) : null
}
// The cars at a glance: where each is, what it charges to, how full it is.
// Targets and "Charge now" are on the Cars page.
/* eslint-disable @typescript-eslint/no-explicit-any */
const carRows = computed(() => cars.value.map((ev: any) => {
  const charging = (ev.power_w ?? 0) > 50 ? `charging ${fmtPower(ev.power_w)}` : null
  const where = ev.connected ? `at ${ev.charger_label ?? 'the charger'}` : 'not plugged in'
  const target = ev.force_charge
    ? `charging now to ${fmt(ev.force_charge.target_soc_pct ?? ev.charge_limit_soc_pct, 0)} %`
    : ev.goal?.target_soc_pct != null && ev.goal?.target_by
      ? `${fmt(ev.goal.target_soc_pct, 0)} % by ${fmtWhen(ev.goal.target_by)}`
      : null
  return {
    id: ev.vehicle_id, label: ev.label ?? ev.vehicle_id, soc: ev.soc_pct as number | null,
    to: '/cars/' + encodeURIComponent(ev.vehicle_id),
    state: [charging, where, target].filter(Boolean).join(' · '),
  }
}))
const guest = computed(() => {
  const at = chargers.value.find((c: any) => c.session?.guest)
  if (!at) return null
  return [(at.power_w ?? 0) > 50 ? `charging ${fmtPower(at.power_w)}` : null, `at ${at.label}`].filter(Boolean).join(' · ')
})

const batteryNow = (d: { sp?: Record<string, unknown>, power_w?: number | null }) =>
  [modeNow(d), Math.abs(d.power_w ?? 0) > 10 ? fmtPower(Math.abs(d.power_w ?? 0)) : null].filter(Boolean).join(' ')
const batteries = computed(() => live.value.filter(d => purposeOf(d) === 'storage'))
const heating = computed(() => live.value.filter(d => purposeOf(d) === 'heating_cooling').map((d) => {
  const p = controllable.value.find(c => c.device_id === d.device_id)
  return { ...d, value: p?.current_value != null ? `${fmt(p.current_value, 1)} ${p.unit ?? ''}`.trim() : null }
}))
// The appliances drawing power right now, the largest first.  A consumer
// without a meter counts with what its forecast expects.
const drawn = (d: { power_w?: number | null, is_virtual?: boolean, forecast_power_w?: number | null }) =>
  (d.is_virtual ? d.forecast_power_w : d.power_w) ?? 0
const APPLIANCES_SHOWN = 4
const appliances = computed(() => live.value.filter(d => purposeOf(d) === 'appliance'))
const running = computed(() => appliances.value
  .filter(d => drawn(d) > 5)
  .sort((a, b) => drawn(b) - drawn(a)))
const kwh = (v: number | null | undefined) => (v == null ? '—' : `${fmt(v, v < 10 ? 2 : 1)} kWh`)
</script>

<template>
  <div v-if="firstStart" class="home">
    <section class="panel full welcome" aria-label="Get started" data-testid="first-start">
      <h2>Welcome to Nornwatt</h2>
      <p class="text-muted-foreground text-sm">
        Nothing is set up yet. Add your devices and Nornwatt starts planning: when to charge
        the battery and the car, and when to run the loads, at the lowest cost.
      </p>
      <ol class="steps">
        <li>
          <span class="step-mark" :class="{ done: homeAssistant }">
            <Check v-if="homeAssistant" class="size-4" /><template v-else>1</template>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block font-medium">Home Assistant</span>
            <span v-if="homeAssistant" class="link-row-sub" data-testid="ha-connection">Connected to {{ homeAssistant.label }}</span>
            <span v-else class="link-row-sub">Optional: needed for devices that are in Home Assistant.</span>
          </span>
          <RouterLink v-if="!homeAssistant" to="/settings/connections" class="btn btn-neutral">Connect</RouterLink>
        </li>
        <li>
          <span class="step-mark">2</span>
          <span class="min-w-0 flex-1">
            <span class="block font-medium">Add your first device</span>
            <span class="link-row-sub">Start with the meter at the grid connection, then PV, battery, car and loads.</span>
          </span>
          <RouterLink to="/settings/devices" class="btn btn-primary" data-testid="add-first-device">Add a device</RouterLink>
        </li>
        <li>
          <span class="step-mark">3</span>
          <span class="min-w-0 flex-1">
            <span class="block font-medium">Your tariff</span>
            <span class="link-row-sub">What electricity costs, so the plan can find the cheap hours.</span>
          </span>
          <RouterLink to="/settings/tariffs" class="btn btn-neutral">Add a tariff</RouterLink>
        </li>
      </ol>
    </section>
  </div>
  <div v-else class="home">
    <ObservingBanner />
    <div class="home-top">
      <section class="panel" aria-label="Power flow">
        <div class="panel-head">
          <h2>Right now</h2>
          <span class="ev-actions-spacer" />
          <RouterLink to="/devices" class="section-link">All devices ›</RouterLink>
        </div>
        <EnergyFlow v-if="tiles.length" :tiles="tiles" :battery-soc-pct="batterySocPct" />
        <p v-else class="text-muted-foreground py-10 text-center text-sm">Waiting for the first readings…</p>
      </section>

      <section class="panel" aria-label="Today in figures" data-testid="today-figures">
        <h2>Today so far</h2>
        <dl class="figures">
          <div><dt>Solar produced</dt><dd>{{ kwh(energy?.solar) }}</dd></div>
          <div><dt>Used in the house</dt><dd>{{ kwh(energy?.used) }}</dd></div>
          <div><dt>From the grid</dt><dd>{{ kwh(energy?.imported) }}</dd></div>
          <div><dt>To the grid</dt><dd>{{ kwh(energy?.exported) }}</dd></div>
          <div title="Share of the energy the house took in today that was its own solar production">
            <dt>From own solar</dt>
            <dd>{{ selfSufficiency == null ? '—' : fmt(selfSufficiency * 100, 0) + ' %' }}</dd>
          </div>
          <div>
            <dt>Cost</dt>
            <dd>{{ eur(savings?.cost) }}</dd>
          </div>
          <div class="figures-wide">
            <dt>Saved by planning</dt>
            <dd :class="gainClass(savings?.saving)" data-testid="today-saving">
              {{ eur(savings?.saving, true) }}
              <RouterLink to="/savings" class="section-link">Savings ›</RouterLink>
            </dd>
            <span v-if="savings && Math.abs(savings.saving - savings.booked) >= 0.005" class="link-row-sub" style="white-space:normal">
              {{ eur(savings.booked, true) }} already realised,
              {{ eur(savings.saving - savings.booked, true) }}
              {{ savings.saving >= savings.booked ? 'in energy stored for later' : 'less stored energy than at midnight' }}
            </span>
          </div>
        </dl>
      </section>
    </div>

    <div class="group-tiles" data-testid="group-tiles">
      <section v-if="batteries.length" class="panel" aria-label="Batteries">
        <div class="panel-head">
          <component :is="PURPOSE_ICONS.storage" class="text-muted-foreground size-4" aria-hidden="true" />
          <h2>Batteries</h2>
          <span class="ev-actions-spacer" />
          <RouterLink to="/batteries" class="section-link">Batteries ›</RouterLink>
        </div>
        <RouterLink v-for="d in batteries" :key="d.device_id" :to="deviceLink(d)" class="tile-row">
          <span class="tile-name">{{ d.label ?? d.device_id }}</span>
          <span class="link-row-sub">{{ batteryNow(d) }}</span>
          <span v-if="d.soc_pct != null" class="soc-bar"><span class="soc-fill block" :style="{ width: Math.min(Math.max(d.soc_pct, 0), 100) + '%' }" /></span>
          <span class="tile-value">{{ d.soc_pct == null ? '—' : fmt(d.soc_pct, 0) + ' %' }}</span>
        </RouterLink>
      </section>

      <section v-if="cars.length" class="panel" aria-label="Cars" data-testid="home-cars">
        <div class="panel-head">
          <component :is="PURPOSE_ICONS.mobility" class="text-muted-foreground size-4" aria-hidden="true" />
          <h2>Cars</h2>
          <span class="ev-actions-spacer" />
          <RouterLink to="/cars" class="section-link">Cars ›</RouterLink>
        </div>
        <RouterLink v-for="c in carRows" :key="c.id" :to="c.to" class="tile-row tile-row-2">
          <span class="min-w-0 flex-1">
            <span class="tile-name block">{{ c.label }}</span>
            <span class="link-row-sub block">{{ c.state }}</span>
          </span>
          <span v-if="c.soc != null" class="soc-bar"><span class="soc-fill block" :style="{ width: Math.min(Math.max(c.soc, 0), 100) + '%' }" /></span>
          <span class="tile-value">{{ c.soc == null ? '—' : fmt(c.soc, 0) + ' %' }}</span>
        </RouterLink>
        <RouterLink v-if="guest" to="/cars" class="tile-row tile-row-2">
          <span class="min-w-0 flex-1">
            <span class="tile-name block">Guest car</span>
            <span class="link-row-sub block truncate">{{ guest }}</span>
          </span>
        </RouterLink>
      </section>

      <section v-if="heating.length" class="panel" aria-label="Heating and cooling">
        <div class="panel-head">
          <component :is="PURPOSE_ICONS.heating_cooling" class="text-muted-foreground size-4" aria-hidden="true" />
          <h2>Heating and cooling</h2>
          <span class="ev-actions-spacer" />
          <RouterLink to="/heating" class="section-link">Heating &amp; cooling ›</RouterLink>
        </div>
        <RouterLink v-for="d in heating" :key="d.device_id" :to="deviceLink(d)" class="tile-row">
          <span class="tile-name">{{ d.label ?? d.device_id }}</span>
          <span v-if="d.value" class="link-row-sub">{{ d.value }}</span>
          <span v-if="modeNow(d)" class="link-row-sub">{{ modeNow(d) }}</span>
          <span class="tile-value">{{ fmtPower(d.power_w) }}</span>
        </RouterLink>
      </section>

      <section v-if="appliances.length" class="panel" aria-label="Appliances">
        <div class="panel-head">
          <component :is="PURPOSE_ICONS.appliance" class="text-muted-foreground size-4" aria-hidden="true" />
          <h2>Appliances</h2>
          <span class="ev-actions-spacer" />
          <RouterLink to="/appliances" class="section-link">Appliances ›</RouterLink>
        </div>
        <RouterLink v-for="d in running.slice(0, APPLIANCES_SHOWN)" :key="d.device_id" :to="deviceLink(d)" class="tile-row">
          <span class="tile-name">{{ d.label ?? d.device_id }}</span>
          <span class="tile-value">{{ fmtDevicePower(d) }}</span>
        </RouterLink>
        <p class="link-row-sub" style="white-space:normal;padding:6px 4px 0">
          <template v-if="!running.length">Nothing is running.</template>
          <template v-else-if="appliances.length > Math.min(running.length, APPLIANCES_SHOWN)">
            {{ appliances.length - Math.min(running.length, APPLIANCES_SHOWN) }} more, idle or small
          </template>
        </p>
      </section>
    </div>

    <div v-if="status?.power_charges" id="power-charges">
      <PowerChargeStatus :pc="status.power_charges" />
    </div>

    <section class="panel full" aria-label="Today">
      <div class="panel-head">
        <h2>Today</h2>
        <span class="link-row-sub" style="white-space:normal">measured so far, expected for the rest of the day</span>
        <span class="ev-actions-spacer" />
        <RouterLink to="/plan" class="section-link">Full plan ›</RouterLink>
      </div>
      <PlotlyChart v-if="todayTraces.length" :traces="todayTraces" :layout="todayLayout" height="300px" data-testid="today-chart" />
      <p v-else class="text-muted-foreground py-8 text-center text-sm">{{ loaded ? 'No data for today yet.' : 'Loading…' }}</p>
    </section>

    <div class="row2-eq">
      <section class="panel" aria-label="What happens next" data-testid="next-up">
        <h2>What happens next</h2>
        <div v-if="next.length" class="link-list">
          <RouterLink v-for="n in next" :key="n.id" :to="n.to" class="link-row next-row">
            <span class="next-time">{{ n.at }}</span>
            <span class="min-w-0 flex-1">
              <span class="block truncate font-medium">{{ n.label }} starts {{ n.then }}</span>
              <span class="link-row-sub">{{ n.inText }} · now {{ n.now }}</span>
            </span>
            <ChevronRight class="link-row-chevron" />
          </RouterLink>
        </div>
        <p v-else class="text-muted-foreground py-4 text-sm">
          {{ loaded ? 'Nothing is planned to change in the planning horizon.' : 'Loading…' }}
        </p>
      </section>

      <section class="panel" aria-label="Prices ahead">
        <div class="panel-head">
          <h2>Prices ahead</h2>
          <span v-if="priceRange" class="link-row-sub" style="white-space:normal">lowest {{ priceRange.lo }} · highest {{ priceRange.hi }}</span>
        </div>
        <PlotlyChart
          v-if="priceTraces.length" :traces="priceTraces" height="220px"
          :layout="{ xaxis: { type: 'date', tickformat: '%H' }, yaxis: { title: 'ct/kWh' }, showlegend: false, ...nowMarker }"
        />
        <p v-else class="text-muted-foreground py-4 text-sm">{{ loaded ? 'No prices available.' : 'Loading…' }}</p>
      </section>
    </div>

  </div>
</template>

<style scoped>
.home-top { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr); gap: 14px; margin-bottom: 14px; }
@media (max-width: 1000px) { .home-top { grid-template-columns: minmax(0, 1fr); } }
.figures { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 18px; }
.figures dt { color: var(--muted-foreground); font-size: .76rem; }
.figures dd { font-size: 1.25rem; font-weight: 650; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }
.figures-wide { grid-column: 1 / -1; padding-top: 12px; border-top: 1px solid var(--border); }
.figures-wide dd { display: flex; align-items: baseline; gap: 12px; }
.welcome { display: flex; flex-direction: column; gap: 12px; max-width: 760px; }
.steps { display: flex; flex-direction: column; gap: 0; margin-top: 4px; }
.steps li { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-top: 1px solid var(--border); flex-wrap: wrap; }
.step-mark { flex: none; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 999px; background: var(--muted); color: var(--muted-foreground); font-weight: 650; font-size: .85rem; }
.step-mark.done { background: var(--success-soft); color: var(--success); }
.next-time { min-width: 3.2rem; flex: none; white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 650; color: var(--primary); }
</style>
