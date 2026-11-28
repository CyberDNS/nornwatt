<script setup lang="ts">
import { ChevronRight } from '@lucide/vue'
import type { Ref } from 'vue'
import type { Status } from '../composables/usePowerFlow'
import { computed, inject, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchLearned } from '../api.js'
import { labelOf } from '../composables/useStatus.js'
import { deviceLink, learnedDeviceId } from '../lib/deviceLinks'
import { learnedHeadline, learnedStatus, learnedTitle } from '../lib/learned'
import { PURPOSE_ORDER, PURPOSE_TITLES, purposeOf } from '../lib/purposes'
import { vehicles } from '../stores/inventory'

// The past, turned into knowledge: everything Nornwatt has learned from what
// it measured, by what the devices are for.  Which models exist, whether
// planning uses them and how accurate they are.  The charts of a model are on
// its device's page: what was learned under Past, the forecast it gives under
// Future.
/* eslint-disable @typescript-eslint/no-explicit-any */
const items = ref<any[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    items.value = await fetchLearned({ summary: true })
  } catch (e) {
    error.value = String((e as Error).message ?? e)
  } finally {
    loading.value = false
  }
})

const status = inject('status') as Ref<Status | null>
/** What the device of a model is for; a model without a known device counts as an appliance. */
function purpose(item: any): string {
  const id = learnedDeviceId(item)
  const device = (status.value?.devices ?? []).find(d => d.device_id === id)
  return device ? purposeOf(device) : 'appliance'
}
const ABOUT: Record<string, string> = {
  generation: 'The PV system learned from its measured production against past weather forecasts: orientation, tilt, peak power, shading and snow. Feeds the solar forecast.',
  storage: 'Efficiency and constant self-consumption of each battery, from the energy charged and discharged against the change of the stored energy. Tells the planner what shifting and holding energy really costs.',
  heating_cooling: 'How much heating and cooling consume per day, from the outdoor temperature and the kind of day; and for the loads Nornwatt runs, how fast their value drifts while idle and moves while running.',
  appliance: 'Daily energy per consumer from the kind of day, spread over the day with a learned hourly shape. Feeds the consumption forecast.',
}
const groups = computed(() => PURPOSE_ORDER
  .map(p => ({ id: p, title: PURPOSE_TITLES[p], about: ABOUT[p] ?? '', items: items.value.filter(i => purpose(i) === p) }))
  .filter(g => g.items.length))

const counts = computed(() => {
  const ok = items.value.filter(i => learnedStatus(i).cls === 'pill-ok').length
  return { ok, total: items.value.length }
})

function link(item: any): string {
  const id = learnedDeviceId(item)
  const isCar = vehicles.value.some(v => v.vehicle_id === id)
  return deviceLink({ device_id: id, category: isCar ? 'vehicle' : null }) + '#learned'
}
const name = (item: any) => item.label ?? labelOf(learnedDeviceId(item))
</script>

<template>
  <div>
    <div v-if="loading" class="text-muted-foreground py-4 text-sm">Loading…</div>
    <div v-else-if="error" class="panel ev-error">Could not load the learned models: {{ error }}</div>
    <div v-else-if="!items.length" class="panel empty-state">
      <h2>Nothing is learned yet</h2>
      <p>
        Give a consumer a learned forecast, or add a battery or a load kept between two thresholds
        (aquarium cooler, AC, …), and what Nornwatt learns about it appears here.
      </p>
      <RouterLink class="btn btn-primary" to="/settings/devices">Open device settings</RouterLink>
    </div>

    <template v-else>
      <p class="panel-hint" style="margin:0 0 14px">
        Learned from what was measured: {{ counts.ok }} of {{ counts.total }} models are in use by the planner.
        Open a device for the charts: what was learned under Past, the forecast it gives under Future.
      </p>
      <div v-for="g in groups" :key="g.id" class="panel full" :data-testid="'learned-' + g.id">
        <h2>{{ g.title }}</h2>
        <p class="panel-hint">{{ g.about }}</p>
        <div class="link-list">
          <RouterLink v-for="i in g.items" :key="i.id" :to="link(i)" class="link-row">
            <span class="link-row-main">{{ name(i) }} <span class="link-row-sub">· {{ learnedTitle(i) }}</span></span>
            <span class="link-row-sub hidden sm:inline">{{ learnedHeadline(i) }}</span>
            <span :class="['pill', learnedStatus(i).cls]">{{ learnedStatus(i).text }}</span>
            <ChevronRight class="link-row-chevron" />
          </RouterLink>
        </div>
      </div>
    </template>
  </div>
</template>
