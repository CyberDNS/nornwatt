<script setup lang="ts">
import type { Ref } from 'vue'
import type { Status } from '../composables/usePowerFlow'
import type { LiveDevice } from '../composables/useLiveDevices'
import { ChevronRight, CornerDownRight } from '@lucide/vue'
import { computed, inject } from 'vue'
import { RouterLink } from 'vue-router'
import { useLiveDevices } from '../composables/useLiveDevices'
import { deviceLink } from '../lib/deviceLinks'
import { fmt, fmtDevicePower } from '../lib/format'
import { CONTROL_TITLES, controlLevel, PURPOSE_ORDER, PURPOSE_TITLES, purposeOf } from '../lib/purposes'
import { chargerOccupant, chargers } from '../stores/inventory'

// Every device of the house by what it is for, with its live figures; a row
// opens the device's page.  A switch that executes another device's plan is
// part of that device and named on its row.  Cars come before chargers; a
// charger with a car plugged in is shown under that car.
const status = inject('status') as Ref<Status | null>
const devices = useLiveDevices(status, { primary: true })

interface Row { d: LiveDevice, nested?: boolean }
interface Section { title: string | null, rows: Row[] }

/** Cars, each with the charger it is plugged in at, then the chargers that are free. */
function mobility(list: LiveDevice[]): Section[] {
  const cars = list.filter(d => d.category === 'vehicle')
  const boxes = list.filter(d => d.category === 'charger')
  const others = list.filter(d => d.category !== 'vehicle' && d.category !== 'charger')
  const at = new Map<string, LiveDevice>() // car → the charger it is plugged in at
  for (const box of boxes) {
    const session = chargers.value.find(c => c.charger_id === box.device_id)
    const car = session?.plugged && !session.session?.guest ? session.session?.vehicle_id : null
    if (car && cars.some(c => c.device_id === car)) at.set(car, box)
  }
  const taken = new Set([...at.values()].map(b => b.device_id))
  const free = boxes.filter(b => !taken.has(b.device_id))
  return [
    { title: 'Cars', rows: cars.flatMap(c => (at.has(c.device_id) ? [{ d: c }, { d: at.get(c.device_id)!, nested: true }] : [{ d: c }])) },
    { title: 'Chargers', rows: [...free, ...others].map(d => ({ d })) },
  ].filter(s => s.rows.length)
}

const groups = computed(() => PURPOSE_ORDER
  .map((p) => {
    const list = devices.value.filter(d => purposeOf(d) === p)
    return {
      id: p, title: PURPOSE_TITLES[p], count: list.length,
      sections: p === 'mobility' ? mobility(list) : [{ title: null, rows: list.map(d => ({ d })) }] as Section[],
    }
  })
  .filter(g => g.count))

const labelOf = (id: string | null | undefined) =>
  (status.value?.devices ?? []).find(d => d.device_id === id)?.label ?? id
const mode = (d: { sp?: Record<string, unknown> }) => (d.sp?.mode ? String(d.sp.mode).replace(/_/g, ' ') : null)
/** A charger without a car answers nothing: that is not a fault. */
const resting = (d: { device_id: string, category?: string | null }) =>
  d.category === 'charger' && chargers.value.some(c => c.charger_id === d.device_id && !c.plugged)
function sub(row: Row): string | null {
  const d = row.d
  if (d.category === 'charger') return row.nested ? 'plugged in here' : chargerOccupant(d.device_id) || null
  if (d.controlled_by) return `through ${labelOf(d.controlled_by)}`
  if (d.is_virtual) return 'no meter of its own'
  return null
}
</script>

<template>
  <div>
    <div v-for="g in groups" :key="g.id" class="panel full" :data-testid="'devices-' + g.id">
      <h2>{{ g.title }}</h2>
      <template v-for="s in g.sections" :key="s.title ?? 'all'">
        <h3 v-if="s.title" class="dev-subhead">{{ s.title }}</h3>
        <div class="link-list" :data-testid="s.title ? 'devices-' + s.title.toLowerCase() : undefined">
          <RouterLink
            v-for="row in s.rows" :key="row.d.device_id" :to="deviceLink(row.d)" class="link-row"
            :class="{ 'link-row-nested': row.nested }"
          >
            <CornerDownRight v-if="row.nested" class="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
            <span
              class="status-dot" :class="row.d.available ? 'on' : resting(row.d) ? 'idle' : 'off'"
              :title="row.d.available ? 'online' : resting(row.d) ? 'nothing connected' : 'not responding'"
            />
            <span class="link-row-main">
              {{ row.d.label ?? row.d.device_id }}
              <span v-if="sub(row)" class="link-row-sub">· {{ sub(row) }}</span>
            </span>
            <span
              v-if="controlLevel(row.d) !== 'measured'" class="pill hidden sm:inline"
              :class="controlLevel(row.d) === 'controlled' ? 'pill-ok' : 'pill-off'" :title="CONTROL_TITLES[controlLevel(row.d)]"
            >{{ controlLevel(row.d) === 'controlled' ? (mode(row.d) && !resting(row.d) ? mode(row.d) : 'controlled') : 'observing' }}</span>
            <!-- The state of charge is the car's: not repeated on the charger under it. -->
            <span v-if="row.d.soc_pct != null && !row.nested" class="devrow-soc">
              <span class="soc-bar"><span class="soc-fill block" :style="{ width: Math.min(Math.max(row.d.soc_pct, 0), 100) + '%' }" /></span>
              <span class="link-row-value">{{ fmt(row.d.soc_pct, 0) }} %</span>
            </span>
            <span class="link-row-value devrow-power" :class="{ ok: (row.d.power_w ?? 0) < -10 }">{{ fmtDevicePower(row.d) }}</span>
            <ChevronRight class="link-row-chevron" />
          </RouterLink>
        </div>
      </template>
    </div>
    <div v-if="!groups.length" class="text-muted-foreground py-4 text-sm">{{ status ? 'No devices yet.' : 'Loading…' }}</div>
  </div>
</template>

<style scoped>
.status-dot.idle { background: var(--muted-foreground); opacity: .45; }
.dev-subhead { font-size: .74rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted-foreground); margin: 10px 6px 2px; }
.dev-subhead:first-of-type { margin-top: 0; }
/* A charger under the car that is plugged in there: one unit, no line between them. */
.link-row-nested { border-top: none !important; padding-top: 2px; padding-left: 14px; }
</style>
