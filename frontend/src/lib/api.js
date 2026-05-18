const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

/**
 * Fetch all available K-pop groups.
 * @returns {Promise<Array<{name: string, generation: string, company: string}>>}
 */
export async function fetchGroups() {
  const res = await fetch(`${API_BASE}/api/groups`);
  if (!res.ok) throw new Error('Failed to fetch groups');
  return (await res.json()).groups;
}

/**
 * Fetch the release history for a group.
 * @param {string} group - Exact group name as returned by fetchGroups
 * @returns {Promise<Array<{title: string, type: string, date: string}>>}
 */
export async function fetchReleases(group) {
  const res = await fetch(`${API_BASE}/api/releases?group=${encodeURIComponent(group)}`);
  if (!res.ok) throw new Error('Failed to fetch releases');
  return (await res.json()).releases;
}

/**
 * Request a release prediction for a group.
 * @param {string} group - Exact group name as returned by fetchGroups
 * @returns {Promise<object>} Prediction result with pred_date_low/med/high and pred_days_*
 */
export async function predictNextRelease(group) {
  const res = await fetch(`${API_BASE}/api/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ group }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Prediction failed');
  }
  return res.json();
}
