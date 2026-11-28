<script setup>
import { ChevronRight } from '@lucide/vue'
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import PlotlyChart from '../components/PlotlyChart.js'
import RangeButtons from '../components/RangeButtons.vue'
import { savingsLink } from '../lib/deviceLinks'
import { gainClass } from '../lib/format'
import { useSavings } from '../composables/useSavings.js'

// The past in money: what the house cost with Nornwatt against a simulated
// house without it, on the same load, PV and prices.  The saving counts the
// energy still stored; what each car, the batteries and each controlled
// device contributed is listed with a link to the page that shows it.
const {
  RANGES, range, pending, loaded, error, load, eur, kwh, buckets, totals, allTime, pct, stored, bucketLabel,
  savingTraces, cumulativeTraces, costOverlayTraces, headline, storedChange, panels,
  savingTitle, savingLayout, cumulativeLayout, costLayout,
} = useSavings()
onMounted(() => load(range.value))

// The stored part of the saving, in words that fit its sign: more energy
// held for later than at the start of the window, or less (it was used, or
// what is left is worth less than it cost).
const storedLabel = computed(() => ((storedChange.value ?? 0) >= 0
  ? { short: 'in energy stored for later', row: 'Energy stored for later',
      about: 'more than without Nornwatt, worth the mean import price of the last 24 h minus what it cost to store' }
  : { short: 'less stored energy than at the start', row: 'Less stored energy than at the start',
      about: 'the lead in stored energy shrank over this window: it was used, or is worth less than it cost' }))
</script>

<template>
  <div>
    <RangeButtons :ranges="RANGES" :active="pending ?? range" @pick="load" />

    <div v-if="error" class="bad" style="margin-bottom:8px;font-size:.82rem">⚠ {{ error }}</div>

    <div v-if="loaded && !buckets.length" class="panel savings-empty">
      <h2>No savings recorded in this window</h2>
      <p>
        Savings are booked per 15-minute slot by comparing the real house with a
        simulated uncontrolled house on the same load, PV and prices. The first
        numbers appear a few minutes after start.
      </p>
    </div>

    <template v-else-if="totals">
      <div class="kpis savings-kpis">
        <div class="card" data-testid="savings-headline">
          <div class="k">Saved</div>
          <div class="v" :class="gainClass(headline)">{{ eur(headline, true) }}</div>
          <div v-if="pct != null" class="savings-sub">{{ pct.toFixed(1) }} % of the cost without Nornwatt</div>
          <template v-if="storedChange != null">
            <div class="savings-sub" data-testid="savings-realised">{{ eur(totals.real, true) }} realised</div>
            <div class="savings-sub" data-testid="savings-stored">{{ eur(storedChange, true) }} {{ storedLabel.short }}</div>
          </template>
        </div>
        <div class="card">
          <div class="k">Without Nornwatt</div>
          <div class="v">{{ eur(totals.uncontrolled_cost) }}</div>
          <div class="savings-sub">simulated · grid bill {{ eur(totals.uncontrolled_bill) }}</div>
        </div>
        <div class="card">
          <div class="k">With Nornwatt</div>
          <div class="v">{{ eur(totals.real_cost) }}</div>
          <div class="savings-sub">real · grid bill {{ eur(totals.real_bill) }}</div>
        </div>
        <div class="card">
          <div class="k">Still stored</div>
          <div class="v">{{ kwh(stored.real.kwh) }}</div>
          <div class="savings-sub">without Nornwatt {{ kwh(stored.uncontrolled.kwh) }}</div>
        </div>
        <div v-if="allTime" class="card">
          <div class="k">All time</div>
          <div class="v" :class="gainClass(allTime.real_with_stored ?? allTime.real)">{{ eur(allTime.real_with_stored ?? allTime.real, true) }}</div>
          <div class="savings-sub">over {{ (allTime.hours / 24).toFixed(1) }} days</div>
        </div>
      </div>

      <div class="panel full" data-testid="savings-overlay">
        <h2>Cost per {{ bucketLabel }}: without and with Nornwatt</h2>
        <p class="panel-hint">
          Both houses on the same consumption, PV and prices. Where the solid line runs below the dashed one,
          Nornwatt saved; where it runs above, it spent more, usually to charge for later. The gap is what is
          realised; energy still stored is not in it yet.
        </p>
        <PlotlyChart :traces="costOverlayTraces" :layout="costLayout" height="280px" />
      </div>

      <div v-if="panels.length" class="panel full" data-testid="savings-breakdown">
        <h2>Where it comes from</h2>
        <div class="link-list">
          <RouterLink v-for="p in panels" :key="p.id" :to="savingsLink(p)" class="link-row">
            <span class="link-row-main">{{ p.label }}</span>
            <span class="link-row-value" :class="gainClass(p.saving)">{{ eur(p.saving, true) }}</span>
            <ChevronRight class="link-row-chevron" />
          </RouterLink>
          <div v-if="storedChange != null" class="link-row" data-testid="savings-stored-row">
            <span class="link-row-main">
              {{ storedLabel.row }}
              <span class="link-row-sub" style="white-space:normal">· {{ storedLabel.about }}</span>
            </span>
            <span class="link-row-value" :class="gainClass(storedChange)">{{ eur(storedChange, true) }}</span>
            <span class="link-row-chevron" />
          </div>
          <div class="link-row savings-total">
            <span class="link-row-main">Saved</span>
            <span class="link-row-value" :class="gainClass(headline)">{{ eur(headline, true) }}</span>
            <span class="link-row-chevron" />
          </div>
        </div>
      </div>

      <div class="row2-eq">
        <div class="panel">
          <h2>Saving per {{ savingTitle }}</h2>
          <p class="panel-hint">What each {{ bucketLabel === 'hour' ? 'step' : bucketLabel }} realised, without the energy still stored.</p>
          <PlotlyChart :traces="savingTraces" :layout="savingLayout" height="260px" />
        </div>
        <div class="panel">
          <h2>Saving over time</h2>
          <p class="panel-hint">Added up over the window. Stored energy turns into a realised saving when it is used.</p>
          <PlotlyChart :traces="cumulativeTraces" :layout="cumulativeLayout" height="260px" />
        </div>
      </div>

      <p class="savings-note">
        Compared against a simulated uncontrolled house on the same load, PV and prices:
        its batteries charge from PV surplus only and cover the household load, and cars charge
        as late as possible to reach their charge plan. Battery wear counts in both houses: each kWh
        stored costs the battery's purchase price ÷ (cycle life × capacity). Stored energy is costed when it is used,
        at what it cost to store it (ledger); charging saves nothing by itself, the saving is realised
        when the energy replaces grid power. Until then it counts as "still stored": the energy one
        house holds beyond the other, valued at the mean import price of the last 24 h
        minus what it cost to store.
      </p>
    </template>
  </div>
</template>

<style scoped>
.savings-total { font-weight: 650; border-top: 2px solid var(--border); }
.savings-total .link-row-main { font-weight: 650; }
.link-row-chevron:empty { width: 16px; flex: none; }
</style>
