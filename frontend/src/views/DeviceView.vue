<script setup lang="ts">
import type { Ref } from 'vue'
import type { Status } from '../composables/usePowerFlow'
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { fetchControllable, fetchLearned } from '../api.js'
import ControllableDeviceCard from '../components/ControllableDeviceCard.vue'
import DeviceCard from '../components/DeviceCard.vue'
import DeviceControls from '../components/DeviceControls.vue'
import DeviceHistory from '../components/DeviceHistory.vue'
import DeviceSavings from '../components/DeviceSavings.vue'
import LearnedModel from '../components/LearnedModel.vue'
import TimeSection from '../components/TimeSection.vue'
import { isPart, useLiveDevices } from '../composables/useLiveDevices'
import { usePageTitle } from '../composables/usePageTitle'
import { planVersion } from '../composables/useStatus.js'
import { deviceLink, deviceNav, learnedDeviceId } from '../lib/deviceLinks'
import { fmt, fmtPower } from '../lib/format'
import { learnedHasForecast, learnedTitle } from '../lib/learned'
import { CONTROL_TITLES, controlLevel, KIND_TITLES } from '../lib/purposes'
import { navItem } from '../nav'
import { chargerOccupant, chargers, vehicles } from '../stores/inventory'

// One device.  Every kind of device has the same page, in the order of time:
// now (state and control), future (plan and forecast), past (what was
// measured, what it saved, what was learned from it).  A section the device
// has nothing for says why, instead of being left out.
/* eslint-disable @typescript-eslint/no-explicit-any */
const route = useRoute()
const router = useRouter()
const status = inject('status') as Ref<Status | null>
const refresh = inject('refresh') as () => Promise<void>
const devices = useLiveDevices(status)

const id = computed(() => String(route.params.id ?? ''))
const device = computed(() => devices.value.find(d => d.device_id === id.value) ?? null)
const category = computed(() => device.value?.category ?? null)

// A switch that executes another device's plan is part of that device.
watch(device, (d) => {
  if (d && isPart(d)) router.replace({ path: deviceLink(d), hash: route.hash })
}, { immediate: true })
/** The switch this device is switched through. */
const through = computed(() => devices.value.find(d => d.device_id === device.value?.controlled_by) ?? null)

const nav = computed(() => deviceNav(device.value))
usePageTitle(
  () => device.value?.label ?? (status.value ? 'Unknown device' : ''),
  () => {
    const item = navItem(nav.value)
    return item ? [{ title: item.title, to: item.to }] : []
  },
  nav,
)

// ── plan and learned models of this device ──
const planned = ref<any | null>(null)
const learned = ref<any[]>([])
const learnedLoaded = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

async function loadPlan() {
  try {
    planned.value = ((await fetchControllable())?.devices ?? []).find((d: any) => d.device_id === id.value) ?? null
  } catch { /* keep the last plan */ }
}
async function loadLearned() {
  try {
    learned.value = (await fetchLearned({ deviceId: id.value })).filter((i: any) => learnedDeviceId(i) === id.value)
  } catch { /* the section says that nothing is learned */ }
  learnedLoaded.value = true
  // A link from the Learning overview points at this section.
  if (route.hash === '#learned' && learned.value.length) {
    await nextTick()
    document.getElementById('learned')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}
function load() { loadPlan(); loadLearned() }
onMounted(() => { load(); timer = setInterval(loadPlan, 60_000) })
onUnmounted(() => clearInterval(timer))
watch(id, load)
watch(planVersion, loadPlan)

const forecasts = computed(() => learned.value.filter(learnedHasForecast))

// ── battery: what is stored and what it cost ──
const ledger = computed(() => (status.value?.ledger ?? []).find(l => l.device_id === id.value) ?? null)

// ── charger: who charges here ──
const charger = computed(() => chargers.value.find(c => c.charger_id === id.value) ?? null)
const defaultCar = computed(() => vehicles.value.find(v => v.vehicle_id === charger.value?.default_vehicle) ?? null)
const resting = computed(() => category.value === 'charger' && charger.value != null && !charger.value.plugged)

// ── a load kept between two thresholds: its value and band ──
const band = computed(() => (planned.value?.bottom_threshold != null
  ? { unit: planned.value.unit, bottom: planned.value.bottom_threshold, top: planned.value.top_threshold }
  : null))
const note = computed(() => {
  if (category.value === 'charger') return chargerOccupant(id.value) || null
  if (expected.value) return expected.value
  if (planned.value?.current_value != null) return `${fmt(planned.value.current_value, 1)} ${planned.value.unit ?? ''}`
  return null
})

const level = computed(() => (device.value ? controlLevel(device.value) : 'measured'))

// ── why a section has nothing ──
const noFuture = computed(() => {
  switch (category.value) {
    case 'pv': return 'The solar forecast comes from the forecast service set up under Settings; it is shown on the Plan page.'
    case 'meter': return 'A meter is measured, not planned. What is expected to flow through the grid connection is on the Plan page.'
    case 'sensor': return 'A sensor is an input for other devices; nothing is planned for it.'
    case 'charger': return 'Charging is planned for the car that is plugged in here; the plan is on the car\'s page.'
    default: return 'Nornwatt does not control this device and has no forecast for it yet.'
  }
})
// A consumer without a meter: what its forecast expects it to draw now.
const expected = computed(() => (device.value?.is_virtual && device.value.forecast_power_w != null
  ? `about ${fmtPower(device.value.forecast_power_w)} expected now (not measured)` : null))
const noSavings = computed(() => {
  if (category.value === 'battery') return null // linked to the batteries together, below
  if (category.value === 'charger') return null
  if (level.value !== 'measured') return 'nothing is booked for this device yet. The first figures appear a few minutes after the start.'
  return 'Nornwatt only measures this device. It decides nothing here, so there is nothing it could have saved.'
})
const noLearned = computed(() => {
  switch (category.value) {
    case 'meter': case 'sensor': case 'charger':
      return 'nothing is learned about this kind of device.'
    case 'pv': return 'the solar forecast is not a learned one. With the learned solar forecast, what Nornwatt found out about the PV system appears here.'
    default: return 'nothing is learned about this device yet.'
  }
})
</script>

<template>
  <div v-if="device && !isPart(device)" :key="id">
    <TimeSection when="now">
      <div class="full device-now">
        <DeviceCard :device="device" :note="note" :resting="resting" class="bg-card">
          <dl class="facts">
            <div><dt>Kind</dt><dd>{{ KIND_TITLES[category ?? ''] ?? 'Device' }}</dd></div>
            <div><dt>Nornwatt</dt><dd data-testid="control-level">{{ device.is_virtual ? 'No meter of its own, derived' : CONTROL_TITLES[level] }}</dd></div>
            <div v-if="through" data-testid="switched-through">
              <dt>Switched through</dt>
              <dd>
                {{ through.label ?? through.device_id }}
                <span class="link-row-sub">· {{ fmtPower(through.power_w) }}{{ through.available === false ? ' · not responding' : '' }}</span>
              </dd>
            </div>
            <template v-if="ledger">
              <div><dt>Stored</dt><dd>{{ fmt(ledger.stored_energy_kwh, 1) }} of {{ fmt(ledger.capacity_kwh, 1) }} kWh</dd></div>
              <div>
                <dt>Cost of the stored energy</dt>
                <dd>{{ fmt(ledger.cost_basis_eur_per_kwh * 100, 1) }} ct/kWh <RouterLink class="section-link" to="/batteries#ledger">Ledger ›</RouterLink></dd>
              </div>
            </template>
            <div v-if="defaultCar">
              <dt>Default car</dt>
              <dd><RouterLink class="section-link" :to="'/cars/' + encodeURIComponent(defaultCar.vehicle_id)">{{ defaultCar.label }} ›</RouterLink></dd>
            </div>
            <div v-if="device.available === false && !resting"><dt>State</dt><dd class="bad">Not responding</dd></div>
          </dl>
        </DeviceCard>
      </div>
      <DeviceControls :device-id="id" @changed="refresh(); loadPlan()" />
    </TimeSection>

    <TimeSection when="future" hint="what is planned and expected">
      <div v-if="planned" class="full panel" data-testid="device-plan">
        <h3>Plan</h3>
        <div class="ctrl-list">
          <ControllableDeviceCard :device="planned" />
        </div>
      </div>
      <div v-for="item in forecasts" :key="item.id" class="full panel" data-testid="device-forecast">
        <h3>Forecast</h3>
        <LearnedModel :item="item" part="forecast" />
      </div>
      <p v-if="!planned && !forecasts.length && learnedLoaded" class="section-note" data-testid="device-future-none">
        {{ noFuture }}
        <RouterLink v-if="category === 'pv' || category === 'meter'" class="section-link" to="/plan">Plan ›</RouterLink>
        <RouterLink v-if="defaultCar" class="section-link" :to="'/cars/' + encodeURIComponent(defaultCar.vehicle_id)">{{ defaultCar.label }} ›</RouterLink>
      </p>
    </TimeSection>

    <TimeSection when="past" hint="what happened and what was learned from it">
      <DeviceHistory :device-id="id" :category="category" :value="band" />

      <p v-if="category === 'battery'" id="saved" class="section-note" data-testid="device-savings-link">
        <b>What it saved:</b> the batteries are accounted for together, as one storage: which battery took or gave a
        kilowatt-hour does not change what the house paid.
        <RouterLink class="section-link" to="/batteries#saved">Savings of the batteries ›</RouterLink>
      </p>
      <p v-else-if="category === 'charger' && defaultCar" id="saved" class="section-note" data-testid="device-savings-link">
        <b>What it saved:</b> what charging here saved is shown with the car.
        <RouterLink class="section-link" :to="'/cars/' + encodeURIComponent(defaultCar.vehicle_id) + '#saved'">{{ defaultCar.label }} ›</RouterLink>
      </p>
      <DeviceSavings v-else :group="id" :reason="noSavings ?? undefined" />

      <div v-for="item in learned" id="learned" :key="item.id" class="full panel">
        <h3>What was learned<span class="link-row-sub"> · {{ learnedTitle(item) }}</span></h3>
        <LearnedModel :item="item" part="learned" @refresh="loadLearned" />
      </div>
      <p v-if="learnedLoaded && !learned.length" class="section-note" data-testid="device-learned-none">
        <b>What was learned:</b> {{ noLearned }}
      </p>
    </TimeSection>

    <p class="footnote">
      <RouterLink class="section-link" to="/settings/devices">Change this device in Settings ›</RouterLink>
    </p>
  </div>

  <div v-else-if="status && !device" class="panel empty-state">
    <h2>Unknown device “{{ id }}”</h2>
    <p>It may have been renamed or removed.</p>
    <RouterLink class="btn btn-neutral" to="/devices">All devices</RouterLink>
  </div>
  <div v-else class="text-muted-foreground py-4 text-sm">Loading…</div>
</template>
