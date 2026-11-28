<script setup>
import { computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import PlotlyChart from './PlotlyChart.js'
import RangeButtons from './RangeButtons.vue'
import { useSavings } from '../composables/useSavings.js'
import { gainClass } from '../lib/format'

// What one savings group saved: the batteries together, their wear, a car
// (kept per charger), or a controlled device.  On short ranges the chart
// compares the real device with the uncontrolled one.  A device Nornwatt does
// not control has nothing to show here; the section then says so (`reason`).
const props = defineProps({
  // The group id of /api/savings: "batteries", "battery_wear", a charger id or a device id.
  group: { type: String, default: null },
  title: { type: String, default: 'What it saved' },
  // The id of the section, for links from the Savings page (#saved, #wear).
  anchor: { type: String, default: 'saved' },
  // Why there is nothing to show, for a device without a savings group.
  reason: { type: String, default: null },
})

const route = useRoute()
const { RANGES, range, pending, loaded, load, eur, panels, buckets } = useSavings()
const panel = computed(() => (props.group ? panels.value.find(p => p.id === props.group) ?? null : null))
onMounted(() => load(range.value))

// A link from the Savings page points at this section.
watch([loaded, panel], async () => {
  if (!loaded.value || route.hash !== '#' + props.anchor) return
  await nextTick()
  document.getElementById(props.anchor)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}, { immediate: true })
</script>

<template>
  <div v-if="loaded && panel" :id="anchor" class="full panel" data-testid="device-savings">
    <div class="panel-head">
      <h3>{{ title }}</h3>
      <span class="savings-group-saving" :class="gainClass(panel.saving)">{{ eur(panel.saving, true) }}</span>
      <span class="ev-actions-spacer" />
      <RangeButtons :ranges="RANGES" :active="pending ?? range" @pick="load" />
    </div>
    <p v-if="!buckets.length" class="panel-hint">Nothing booked in this range yet.</p>
    <p v-else-if="panel.note" class="panel-hint">{{ panel.note }}</p>
    <PlotlyChart v-if="panel.traces.length && buckets.length" :traces="panel.traces" :layout="panel.layout" :height="panel.height" />
    <p v-if="group === 'batteries'" class="footnote">All batteries together: the saving is accounted for the storage as a whole.</p>
  </div>
  <p v-else-if="loaded && reason" :id="anchor" class="section-note" data-testid="device-savings-none">
    <b>{{ title }}:</b> {{ reason }}
  </p>
</template>
