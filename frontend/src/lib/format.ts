// Number formatting shared by the shell and the views.
const DASH = '—'

export function fmt(v: number | null | undefined, decimals = 0): string {
  return v == null ? DASH : Number(v).toFixed(decimals)
}

/** 850 → "850 W", 2310 → "2.31 kW". */
export function fmtPower(w: number | null | undefined): string {
  if (w == null) return DASH
  const abs = Math.abs(w)
  return abs >= 1000 ? `${(w / 1000).toFixed(2)} kW` : `${Math.round(w)} W`
}

/** The power a device draws now: measured, or for a consumer without a meter
 *  what its forecast expects ("≈ 380 W"). */
export function fmtDevicePower(d: { power_w?: number | null, is_virtual?: boolean, forecast_power_w?: number | null }): string {
  return d.is_virtual && d.forecast_power_w != null ? `≈ ${fmtPower(d.forecast_power_w)}` : fmtPower(d.power_w)
}

/** 0.2840 €/kWh → "28.40 ct". */
export function fmtPrice(eurPerKwh: number | null | undefined): string {
  return eurPerKwh == null ? DASH : `${(Number(eurPerKwh) * 100).toFixed(2)} ct`
}

/** Seconds since an ISO timestamp as "12s ago" / "3 min ago". */
export function fmtAgo(iso: string | null | undefined, now = Date.now()): string | null {
  if (!iso) return null
  const sec = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
  return sec < 90 ? `${sec}s ago` : `${Math.round(sec / 60)} min ago`
}

/** *text* broken at spaces into lines of at most ~*width* characters
 *  (a longer word gets a line of its own) — for chart tooltips. */
export function wrapLines(text: string | null | undefined, width = 60): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of (text ?? '').split(' ').filter(Boolean)) {
    if (line && line.length + 1 + word.length > width) {
      lines.push(line)
      line = word
    } else {
      line = line ? `${line} ${word}` : word
    }
  }
  if (line) lines.push(line)
  return lines
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Clock time, always 24 h: "18:14". */
export function fmtTime(at: Date | string | number): string {
  const d = new Date(at)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Day and month: "28.11.". */
export function fmtDate(at: Date | string | number): string {
  const d = new Date(at)
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.`
}

/** "28.11. 18:14" — the format of the chart axes. */
export function fmtDateTime(at: Date | string | number): string {
  return `${fmtDate(at)} ${fmtTime(at)}`
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** A time with its day when that is not today: "18:14", "tomorrow 18:14", "Mon 18:14". */
export function fmtWhen(at: Date | string | number, now: Date = new Date()): string {
  const d = new Date(at)
  const days = Math.round(
    (new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
      - new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()) / 86_400_000,
  )
  if (days === 0) return fmtTime(d)
  if (days === 1) return `tomorrow ${fmtTime(d)}`
  if (days === -1) return `yesterday ${fmtTime(d)}`
  return `${WEEKDAYS[d.getDay()]} ${fmtTime(d)}`
}

/** A day and time for dates further away: "Sat 05.12. 17:28". */
export function fmtDayTime(at: Date | string | number): string {
  const d = new Date(at)
  return `${WEEKDAYS[d.getDay()]} ${fmtDateTime(d)}`
}

/** An amount of money: "−0.54 €"; *signed* adds "+" to gains.  Less than half a cent is "0.00 €". */
export function fmtEur(v: number | null | undefined, signed = false): string {
  if (v == null) return DASH
  const s = `${Math.abs(v).toFixed(2)} €`
  if (v < -0.005) return `−${s}`
  return (signed && v > 0.005 ? '+' : '') + s
}

/** The colour class of a gain or loss: nothing when it rounds to zero. */
export function gainClass(v: number | null | undefined): string {
  if (v == null || Math.abs(v) < 0.005) return ''
  return v > 0 ? 'ok' : 'bad'
}
