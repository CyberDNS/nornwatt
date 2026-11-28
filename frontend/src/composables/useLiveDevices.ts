// The devices of the live status, each merged with its active setpoint and
// sorted by what they are for, for the device cards and the device pages.
import type { Ref } from 'vue'
import type { Status, StatusDevice } from './usePowerFlow'
import { computed } from 'vue'
import { PURPOSE_ORDER, purposeOf } from '../lib/purposes'

export type LiveDevice = StatusDevice & { sp?: Record<string, unknown> }

export interface DeviceFilter {
  categories?: string[]
  purposes?: string[]
  /** Leave out switches that only execute another device's plan: they are
   *  part of that device (a plug and the cooler behind it are one device). */
  primary?: boolean
}

/** A switch that executes another device's plan is a part of that device. */
export function isPart(device: StatusDevice): boolean {
  return device.category === 'switch' && (device.controls?.length ?? 0) > 0
}

export function useLiveDevices(status: Ref<Status | null>, filter: DeviceFilter | string[] = {}) {
  const f: DeviceFilter = Array.isArray(filter) ? { categories: filter } : filter
  return computed<LiveDevice[]>(() => {
    const setpoints = new Map(((status.value?.setpoints ?? []) as { device_id: string }[]).map(s => [s.device_id, s]))
    const order = (d: StatusDevice) => {
      const i = PURPOSE_ORDER.indexOf(purposeOf(d))
      return i < 0 ? PURPOSE_ORDER.length : i
    }
    return (status.value?.devices ?? [])
      .filter(d => !f.categories || f.categories.includes(d.category ?? ''))
      .filter(d => !f.purposes || f.purposes.includes(purposeOf(d)))
      .filter(d => !f.primary || !isPart(d))
      .map(d => ({ ...d, sp: setpoints.get(d.device_id) }))
      .sort((a, b) => order(a) - order(b)
        || (a.label ?? a.device_id).localeCompare(b.label ?? b.device_id))
  })
}
