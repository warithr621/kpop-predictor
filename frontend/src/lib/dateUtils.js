export function fmt(date) {
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
}

export function fmtShort(date) {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function daysFromNow(date) {
  return Math.round((date - new Date()) / 86400000);
}

// Parses an ISO date string safely, avoiding "Invalid Date" from double T suffixes
export function parseISODate(str) {
  return new Date(str.slice(0, 10) + 'T12:00:00');
}

// Returns a Date or null for arbitrary date strings (used in Timeline)
export function toDate(d) {
  const dt = new Date(d);
  return isNaN(dt.getTime()) ? null : dt;
}
