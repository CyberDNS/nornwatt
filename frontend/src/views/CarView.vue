<script setup lang="ts">
import { computed, inject } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ControllableDeviceCard from '../components/ControllableDeviceCard.vue'
import DeviceControls from '../components/DeviceControls.vue'
import DeviceHistory from '../components/DeviceHistory.vue'
import DeviceSavings from '../components/DeviceSavings.vue'
import EvCard from '../components/EvCard.vue'
import TimeSection from '../components/TimeSection.vue'
import { useCars } from '../composables/useCars'
import { usePageTitle } from '../composables/usePageTitle'
import { planning } from '../composables/useStatus.js'
import { chargerOf } from '../stores/inventory'

// One car: #/cars/<vehicle>, matched by vehicle id or label, case-insensitively.
// The same page as every device, in the order of time: now, future, past.
// Also what an iframe in a Home Assistant dashboard shows (…?embed=1): there
// only the car and its charging plan.
const route = useRoute()
const embed = inject('embed', computed(() => false))
const refreshStatus = inject('refresh', async () => {}) as () => Promise<void>
const { cars, chargers, loaded, refresh, planOf } = useCars()

const wanted = computed(() => String(route.params.vehicle ?? '').trim().toLowerCase())
const car = computed(() => cars.value.find(e =>
  e.vehicle_id.toLowerCase() === wanted.value || e.label?.toLowerCase() === wanted.value))
const plan = computed(() => car.value && planOf(car.value.vehicle_id))
// The charger of the car: where it is plugged in, else the one it is the
// default car of.  Its power is the car's charging history, and the savings
// are kept per charger.
const charger = computed(() => (car.value
  ? chargers.value.find(c => c.charger_id === car.value.charger_id)
    ?? chargers.value.find(c => c.default_vehicle === car.value.vehicle_id)
    ?? chargerOf(car.value.vehicle_id)
  : null))
// The savings group is the charger this car is the default car of.
const savingsGroup = computed(() =>
  chargers.value.find(c => c.default_vehicle === car.value?.vehicle_id)?.charger_id ?? null)

usePageTitle(() => car.value?.label ?? (loaded.value ? 'Unknown car' : ''), [{ title: 'Cars', to: '/cars' }])
</script>

<template>
  <div>
    <!-- Without the header (embed mode) the page says itself that a new plan is on its way. -->
    <transition name="fade">
      <p v-if="embed && planning" class="plan-busy" style="margin-bottom:8px">
        <span class="spinner" /> Recalculating plan…
      </p>
    </transition>

    <!-- An embedded car card stays what it was: the car and its charging plan. -->
    <template v-if="car && embed">
      <div class="full">
        <EvCard :key="car.vehicle_id" :ev="car" :chargers="chargers" @refresh="refresh" />
      </div>
      <div v-if="plan" class="full panel">
        <h2>Charging plan</h2>
        <div class="ctrl-list">
          <ControllableDeviceCard :device="plan" />
        </div>
      </div>
    </template>

    <template v-else-if="car">
      <TimeSection when="now">
        <div class="full">
          <EvCard :key="car.vehicle_id" :ev="car" :chargers="chargers" @refresh="refresh" />
        </div>
        <DeviceControls :device-id="car.vehicle_id" @changed="refreshStatus(); refresh()" />
      </TimeSection>

      <TimeSection when="future" hint="what is planned and expected">
        <div v-if="plan" class="full panel" data-testid="device-plan">
          <h3>Charging plan</h3>
          <div class="ctrl-list">
            <ControllableDeviceCard :device="plan" />
          </div>
        </div>
        <p v-else class="section-note">No charging plan yet.</p>
      </TimeSection>

      <TimeSection when="past" hint="what happened and what was learned from it">
        <DeviceHistory :device-id="car.vehicle_id" :power-device-id="charger?.charger_id ?? null" category="vehicle" />
        <p v-if="charger" class="footnote" style="margin:-8px 2px 14px">
          Charging power as measured at
          <RouterLink class="section-link" :to="'/devices/' + encodeURIComponent(charger.charger_id)">{{ charger.label }} ›</RouterLink>
        </p>
        <DeviceSavings
          :group="savingsGroup"
          reason="savings are kept per charger, under its default car. This car is no charger's default car, so its charging counts for the car that is."
        />
        <p class="section-note" data-testid="device-learned-none">
          <b>What was learned:</b> nothing is learned about cars yet. When and how far a car charges comes from its
          charging targets.
        </p>
      </TimeSection>
    </template>

    <div v-else-if="loaded" class="panel empty-state">
      <h2>Unknown car “{{ route.params.vehicle }}”</h2>
      <p v-if="cars.length">Available: {{ cars.map(e => e.vehicle_id).join(', ') }}</p>
      <RouterLink v-if="!embed" class="btn btn-neutral" to="/cars">All cars</RouterLink>
    </div>
  </div>
</template>
