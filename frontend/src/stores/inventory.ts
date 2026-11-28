// What the house has, for parts of the shell that depend on it (navigation,
// status bar, device lists).  One shared copy, refreshed with every new plan.
import { ref, watch } from 'vue'
import { fetchChargers, fetchVehicles } from '../api.js'
import { planVersion } from '../composables/useStatus.js'

export interface Vehicle {
  vehicle_id: string
  label: string
  /** The charger the car is plugged in at right now. */
  charger_id?: string | null
  [key: string]: unknown
}

export interface Charger {
  charger_id: string
  label: string
  plugged?: boolean
  default_vehicle?: string | null
  session?: { vehicle_id?: string | null, guest?: boolean } | null
  [key: string]: unknown
}

export const vehicles = ref<Vehicle[]>([])
export const chargers = ref<Charger[]>([])
/** False until the first answer, so the shell does not flash "no cars". */
export const inventoryLoaded = ref(false)

let started = false

export async function refreshInventory(): Promise<void> {
  try {
    const [list, chs] = await Promise.all([fetchVehicles(), fetchChargers().catch(() => [])])
    vehicles.value = Array.isArray(list) ? list : []
    chargers.value = Array.isArray(chs) ? chs : []
    inventoryLoaded.value = true
  } catch {
    /* keep what we have; the status banner reports an unreachable server */
  }
}

export function startInventory(): void {
  if (started) return
  started = true
  refreshInventory()
  watch(planVersion, refreshInventory)
  setInterval(refreshInventory, 5 * 60_000)
}

/** The charger a car charges at: where it is plugged in, else the one it is the default car of. */
export function chargerOf(vehicleId: string): Charger | null {
  const car = vehicles.value.find(v => v.vehicle_id === vehicleId)
  return chargers.value.find(c => c.charger_id === car?.charger_id)
    ?? chargers.value.find(c => c.default_vehicle === vehicleId)
    ?? null
}

/** Who is at a charger right now, in words. */
export function chargerOccupant(chargerId: string): string {
  const c = chargers.value.find(x => x.charger_id === chargerId)
  if (!c) return ''
  if (!c.plugged) return 'no car plugged in'
  if (c.session?.guest) return 'guest car plugged in'
  const car = vehicles.value.find(v => v.vehicle_id === c.session?.vehicle_id)
  return car ? `${car.label} plugged in` : 'car plugged in'
}
