export function displayBigram(bigram: string): string {
  return bigram.replace(/ /g, '␣')
}

export function fmtDelta(d: number): string {
  const sign = d >= 0 ? '+' : ''
  return `${sign}${d.toFixed(1)}`
}

// Renders a duration given in minutes as HH:MM:SS, for the "time typing" KPI.
export function fmtDurationHMS(minutes: number): string {
  const totalSeconds = Math.round(minutes * 60)
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}
