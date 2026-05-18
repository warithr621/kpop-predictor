export function getAccentColor(generation) {
  return generation === '4th Gen' ? '#f0287a' : '#22d3ee';
}

export function getGlowColor(generation) {
  return generation === '4th Gen'
    ? 'rgba(240, 40, 122, 0.4)'
    : 'rgba(34, 211, 238, 0.4)';
}

export function getGradientEnd(generation) {
  return generation === '4th Gen' ? '#c026d3' : '#6366f1';
}

export function getBadgeClass(generation) {
  return generation === '4th Gen' ? 'gen-badge-4th' : 'gen-badge-5th';
}
