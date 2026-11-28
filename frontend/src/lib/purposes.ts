// What devices are for (core/device_model.py: Purpose): how the UI groups
// them.  The category says how Nornwatt treats a device; the purpose says
// where a user looks for it — a heat pump that is only measured is a consumer
// by category and heating by purpose.
import type { Component } from 'vue'
import { BatteryMedium, Car, Gauge, Heater, Plug, Sun } from '@lucide/vue'

export const PURPOSE_ORDER = ['generation', 'storage', 'mobility', 'heating_cooling', 'appliance', 'metering']

export const PURPOSE_TITLES: Record<string, string> = {
  generation: 'Solar',
  storage: 'Batteries',
  mobility: 'Cars and chargers',
  heating_cooling: 'Heating and cooling',
  appliance: 'Appliances and other loads',
  metering: 'Meters and sensors',
}

export const PURPOSE_ICONS: Record<string, Component> = {
  generation: Sun,
  storage: BatteryMedium,
  mobility: Car,
  heating_cooling: Heater,
  appliance: Plug,
  metering: Gauge,
}

/** For a backend without purposes: the purpose a category stands for. */
const CATEGORY_PURPOSE: Record<string, string> = {
  pv: 'generation', battery: 'storage', vehicle: 'mobility', charger: 'mobility',
  thermal_load: 'heating_cooling', switch: 'appliance', consumer: 'appliance',
  meter: 'metering', sensor: 'metering',
}

export function purposeOf(device: { purpose?: string | null, category?: string | null }): string {
  return device.purpose ?? CATEGORY_PURPOSE[device.category ?? ''] ?? 'appliance'
}

/** What a device is, in the words of its page ("Kind"). */
export const KIND_TITLES: Record<string, string> = {
  pv: 'Solar',
  battery: 'Battery',
  vehicle: 'Car',
  charger: 'Charger',
  thermal_load: 'Heating or cooling load',
  switch: 'Switch',
  consumer: 'Consumer',
  meter: 'Meter',
  sensor: 'Sensor',
}

/** How far Nornwatt is involved with a device. */
export type ControlLevel = 'controlled' | 'observed' | 'measured'

export const CONTROL_TITLES: Record<ControlLevel, string> = {
  controlled: 'Planned and controlled',
  observed: 'Planned, not controlled',
  measured: 'Measured only',
}

export function controlLevel(device: { control?: string | null }): ControlLevel {
  if (device.control === 'active') return 'controlled'
  if (device.control === 'observe') return 'observed'
  return 'measured'
}
