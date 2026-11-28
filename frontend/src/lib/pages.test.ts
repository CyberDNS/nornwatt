import { describe, expect, it } from 'vitest'
import { isPart } from '../composables/useLiveDevices'
import { deviceLink, deviceNav, savingsLink } from './deviceLinks'
import { fmtDateTime, fmtEur, fmtTime, fmtWhen, gainClass } from './format'
import { learnedNothing, learnedStatus } from './learned'
import { controlLevel, purposeOf } from './purposes'

describe('times and money', () => {
  const now = new Date(2026, 10, 28, 17, 0)

  it('shows clock times in 24 hours', () => {
    expect(fmtTime(new Date(2026, 10, 28, 18, 14))).toBe('18:14')
    expect(fmtDateTime(new Date(2026, 10, 5, 7, 5))).toBe('05.11. 07:05')
  })

  it('names the day of a time that is not today', () => {
    expect(fmtWhen(new Date(2026, 10, 28, 20, 14), now)).toBe('20:14')
    expect(fmtWhen(new Date(2026, 10, 29, 18, 14), now)).toBe('tomorrow 18:14')
    expect(fmtWhen(new Date(2026, 10, 30, 15, 29), now)).toBe('Mon 15:29')
  })

  it('gives an amount that rounds to zero neither a sign nor a colour', () => {
    expect(fmtEur(-0.001, true)).toBe('0.00 €')
    expect(gainClass(-0.001)).toBe('')
    expect(fmtEur(0.4, true)).toBe('+0.40 €')
    expect(gainClass(0.4)).toBe('ok')
    expect(fmtEur(-0.54)).toBe('−0.54 €')
    expect(gainClass(-0.54)).toBe('bad')
  })
})

describe('devices that belong together', () => {
  const plug = { device_id: 'cooler_plug', category: 'switch', purpose: 'heating_cooling', controls: ['cooler'] }
  const cooler = { device_id: 'cooler', category: 'thermal_load', purpose: 'heating_cooling', controlled_by: 'cooler_plug' }

  it('treats a switch that executes another device\'s plan as part of that device', () => {
    expect(isPart(plug)).toBe(true)
    expect(isPart(cooler)).toBe(false)
    expect(isPart({ device_id: 'lamp', category: 'switch', controls: [] })).toBe(false)
    expect(deviceLink(plug)).toBe('/devices/cooler')
    expect(deviceLink(cooler)).toBe('/devices/cooler')
  })

  it('files a device under what it is for, not under how it is treated', () => {
    const heatPump = { device_id: 'hp', category: 'consumer', purpose: 'heating_cooling' }
    expect(deviceNav(heatPump)).toBe('heating')
    expect(deviceNav({ category: 'consumer' })).toBe('appliances')
    expect(deviceNav({ category: 'charger' })).toBe('cars')
    expect(deviceNav({ category: 'meter' })).toBe('devices')
    // A backend without purposes: the category decides.
    expect(purposeOf({ category: 'thermal_load' })).toBe('heating_cooling')
  })

  it('tells controlled, observed and measured devices apart', () => {
    expect(controlLevel({ control: 'active' })).toBe('controlled')
    expect(controlLevel({ control: 'observe' })).toBe('observed')
    expect(controlLevel({ control: null })).toBe('measured')
  })
})

describe('links from the savings', () => {
  it('opens the car of a charger\'s savings, not the charger as a car', () => {
    expect(savingsLink({ id: 'wallbox', kind: 'car', vehicle_id: 'banzert' })).toBe('/cars/banzert#saved')
    expect(savingsLink({ id: 'garage', kind: 'car', vehicle_id: null })).toBe('/devices/garage#saved')
  })

  it('opens the section that shows the row', () => {
    expect(savingsLink({ id: 'battery_wear', kind: 'wear' })).toBe('/batteries#wear')
    expect(savingsLink({ id: 'batteries', kind: 'batteries' })).toBe('/batteries#saved')
    expect(savingsLink({ id: 'cooler', kind: 'device' })).toBe('/devices/cooler#saved')
  })
})

describe('learned models', () => {
  const fitted = (model: object) => ({ id: 'x_forecast', status: 'fitted', model })

  it('does not call a model active that only ever saw zero', () => {
    const empty = fitted({ mode: 'level', level_kwh: { all: 0, weekday: 0, weekend: 0 }, mae_kwh: 0 })
    expect(learnedNothing(empty)).toBe(true)
    expect(learnedStatus(empty).text).toBe('No consumption seen')
    const real = fitted({ mode: 'level', level_kwh: { all: 8.9 }, mae_kwh: 1.2 })
    expect(learnedNothing(real)).toBe(false)
    expect(learnedStatus(real).text).toBe('Model active')
  })
})
