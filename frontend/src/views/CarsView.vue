<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import ControllableDeviceCard from '../components/ControllableDeviceCard.vue'
import DeviceHistory from '../components/DeviceHistory.vue'
import DeviceSavings from '../components/DeviceSavings.vue'
import EvCard from '../components/EvCard.vue'
import GuestCard from '../components/GuestCard.vue'
import TimeSection from '../components/TimeSection.vue'
import { useCars } from '../composables/useCars'

// The cars together, in the order of time like every device page: where each
// is and what it is charging to (now), when it is planned to charge (future),
// how it charged and what charging at the right time saved (past).
/* eslint-disable @typescript-eslint/no-explicit-any */
const { cars, chargers, loaded, refresh, planOf } = useCars()

const plans = computed(() => cars.value.map(c => planOf(c.vehicle_id)).filter(Boolean))
// Savings are kept per charger, under its default car.
const saved = computed(() => cars.value
  .map(c => ({ car: c, group: chargers.value.find((ch: any) => ch.default_vehicle === c.vehicle_id)?.charger_id ?? null }))
  .filter(s => s.group))
// Where a car's charging power is measured: where it is plugged in, else the charger it is the default car of.
const chargerIdOf = (c: any): string | null => c.charger_id
  ?? chargers.value.find((ch: any) => ch.default_vehicle === c.vehicle_id)?.charger_id ?? null
const carLink = (id: string) => '/cars/' + encodeURIComponent(id)
</script>

<template>
  <div>
    <template v-if="cars.length">
      <TimeSection when="now">
        <div class="ev-cards full">
          <EvCard
            v-for="ev in cars" :key="ev.vehicle_id" :ev="ev" :chargers="chargers" collapsible
            :to="carLink(ev.vehicle_id)" @refresh="refresh"
          />
        </div>
        <GuestCard v-if="chargers.length" :chargers="chargers" class="full" @refresh="refresh" />
      </TimeSection>

      <TimeSection when="future" hint="when each car is planned to charge">
        <div v-if="plans.length" class="full panel" data-testid="cars-plan">
          <div class="ctrl-list">
            <ControllableDeviceCard v-for="p in plans" :key="p.device_id" :device="p" :to="carLink(p.vehicle_id ?? p.device_id)" />
          </div>
        </div>
        <p v-else class="section-note">No charging plan yet.</p>
      </TimeSection>

      <TimeSection when="past" hint="how each car charged and what charging at the right time saved">
        <DeviceHistory
          v-for="c in cars" :key="c.vehicle_id" :device-id="c.vehicle_id" category="vehicle"
          :power-device-id="chargerIdOf(c)" :title="(c.label ?? c.vehicle_id) + ': charging and state of charge'"
        />
        <DeviceSavings
          v-for="s in saved" :key="s.car.vehicle_id" :group="s.group" :title="(s.car.label ?? s.car.vehicle_id) + ': what it saved'"
          :anchor="'saved-' + s.car.vehicle_id"
        />
        <p v-if="!saved.length" class="section-note">
          Savings are kept per charger, under its default car. No charger has a default car yet.
        </p>
      </TimeSection>
    </template>

    <div v-else-if="loaded" class="panel empty-state">
      <h2>No cars yet</h2>
      <p>Add a vehicle and the charger it uses to plan its charging around prices and PV.</p>
      <RouterLink class="btn btn-primary" to="/settings/devices">Open device settings</RouterLink>
    </div>
    <GuestCard v-if="!cars.length && chargers.length" :chargers="chargers" class="mt-3" @refresh="refresh" />
  </div>
</template>
