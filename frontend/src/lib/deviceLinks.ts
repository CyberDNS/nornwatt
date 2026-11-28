// Where the pages of devices live.  Cars have their own page (it is also what
// dashboards embed); every other device uses the generic device page.  A
// switch that executes another device's plan has no page of its own: it is
// part of that device.
import { purposeOf } from './purposes'

interface Linked {
  device_id: string
  category?: string | null
  purpose?: string | null
  controls?: string[]
}

/** The page of a device. */
export function deviceLink(device: Linked): string {
  if (device.category === 'vehicle') return `/cars/${encodeURIComponent(device.device_id)}`
  const host = device.category === 'switch' ? device.controls?.[0] : undefined
  return `/devices/${encodeURIComponent(host ?? device.device_id)}`
}

/** The sidebar item a device belongs to. */
export function deviceNav(device: { category?: string | null, purpose?: string | null } | null | undefined): string {
  if (!device) return 'devices'
  switch (purposeOf(device)) {
    case 'mobility': return 'cars'
    case 'storage': return 'batteries'
    case 'heating_cooling': return 'heating'
    case 'appliance': return 'appliances'
    default: return 'devices'
  }
}

export interface SavingsGroup {
  id: string
  kind: string
  /** A car group: the car whose page shows it (savings are kept per charger). */
  vehicle_id?: string | null
}

/** The page behind a savings group, at the section that shows it: the
 *  batteries together, their wear, the power charges, a car, a device. */
export function savingsLink(group: SavingsGroup): string {
  if (group.kind === 'batteries') return '/batteries#saved'
  if (group.kind === 'wear') return '/batteries#wear'
  if (group.kind === 'power') return '/#power-charges'
  if (group.kind === 'car' && group.vehicle_id) return `/cars/${encodeURIComponent(group.vehicle_id)}#saved`
  return `/devices/${encodeURIComponent(group.id)}#saved`
}

/** The device a learned model belongs to (`<device>_forecast` for consumption models). */
export function learnedDeviceId(item: { id: string, device_id?: string }): string {
  return item.device_id ?? item.id.replace(/_forecast$/, '')
}
