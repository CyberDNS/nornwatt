<script setup lang="ts">
import type { Ref } from 'vue'
import type { Status } from '../composables/usePowerFlow'
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchControllable } from '../api.js'
import ControllableDeviceCard from '../components/ControllableDeviceCard.vue'
import DeviceCard from '../components/DeviceCard.vue'
import TimeSection from '../components/TimeSection.vue'
import { useLiveDevices } from '../composables/useLiveDevices'
import { planVersion } from '../composables/useStatus.js'
import { deviceLink } from '../lib/deviceLinks'
import { fmt } from '../lib/format'
import { purposeOf } from '../lib/purposes'

// The devices with one purpose (heating and cooling, appliances), whether
// Nornwatt runs them or only measures them: what each does now, and what is
// planned for the ones it runs.  A plug and the device behind it are one device.
const props = defineProps<{ purpose: 'heating_cooling' | 'appliance' }>()

const status = inject('status') as Ref<Status | null>
// The same component shows both pages: the list has to follow the purpose
// when the route changes, not keep the one the component was created with.
const all = useLiveDevices(status, { primary: true })
const live = computed(() => all.value.filter(d => purposeOf(d) === props.purpose))

/* eslint-disable @typescript-eslint/no-explicit-any */
const controllable = ref<any[]>([])
const loaded = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
async function load() {
  try {
    controllable.value = (await fetchControllable())?.devices ?? []
  } catch { /* keep the last plan */ } finally {
    loaded.value = true
  }
}
onMounted(() => { load(); timer = setInterval(load, 60_000) })
onUnmounted(() => clearInterval(timer))
watch(planVersion, load)

const planned = computed(() => controllable.value.filter(p => live.value.some(d => d.device_id === p.device_id)))
const planOf = (id: string) => controllable.value.find(p => p.device_id === id)
const labelOf = (id: string | null | undefined) =>
  (status.value?.devices ?? []).find(d => d.device_id === id)?.label ?? id

/** What the device says about itself: its temperature, and the plug it is switched through. */
function note(d: { device_id: string, controlled_by?: string | null }): string | null {
  const p = planOf(d.device_id)
  const parts = [
    p?.current_value != null ? `${fmt(p.current_value, 1)} ${p.unit ?? ''}`.trim() : null,
    d.controlled_by ? `through ${labelOf(d.controlled_by)}` : null,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : null
}

const WORDS = {
  heating_cooling: {
    plan: 'When each load is planned to run. Loads with a temperature band run when electricity is cheap or PV is available, and always before the temperature leaves the band.',
    emptyTitle: 'No heating or cooling yet',
    empty: 'Add a heater, a boiler or an air conditioner, or mark a consumer (a heat pump that is only measured) as heating or cooling in its settings.',
  },
  appliance: {
    plan: 'When each load is planned to run.',
    emptyTitle: 'No appliances yet',
    empty: 'Add the consumers of the house that have their own meter or plug, so their consumption is forecast one by one.',
  },
}
const words = computed(() => WORDS[props.purpose])
const empty = computed(() => loaded.value && status.value != null && !live.value.length)
</script>

<template>
  <div>
    <template v-if="live.length">
      <TimeSection when="now">
        <div class="dev-cards full">
          <DeviceCard v-for="d in live" :key="d.device_id" :device="d" :to="deviceLink(d)" :note="note(d)" class="bg-card" />
        </div>
      </TimeSection>

      <TimeSection when="future" hint="what is planned">
        <div v-if="planned.length" class="full panel">
          <p class="panel-hint">{{ words.plan }}</p>
          <div class="ctrl-list">
            <ControllableDeviceCard v-for="d in planned" :key="d.device_id" :device="d" />
          </div>
        </div>
        <div v-else class="full panel">
          <p class="panel-hint" style="margin:0">
            Nornwatt only measures these devices; none of them is planned. What they are expected to consume is
            part of the forecast on the <RouterLink class="section-link" to="/plan">Plan ›</RouterLink> page.
          </p>
        </div>
      </TimeSection>

      <p class="footnote">History, savings and what was learned are on each device's page.</p>
    </template>

    <div v-if="empty" class="panel empty-state">
      <h2>{{ words.emptyTitle }}</h2>
      <p>{{ words.empty }}</p>
      <RouterLink class="btn btn-primary" to="/settings/devices">Open device settings</RouterLink>
    </div>
  </div>
</template>
