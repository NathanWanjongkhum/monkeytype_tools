// A leading/trailing space (word-boundary bigrams like " b") collapses under
// normal HTML whitespace rules and becomes indistinguishable from a bare
// "b". Swap in a visible space glyph so it stays legible.
export function displayBigram(bigram: string): string {
  return bigram.replace(/ /g, '␣')
}

export function fmtDelta(d: number): string {
  const sign = d >= 0 ? '+' : ''
  return `${sign}${d.toFixed(1)}`
}
