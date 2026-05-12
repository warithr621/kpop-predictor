const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export async function fetchGroups() {
  const res = await fetch(`${API_BASE}/api/groups`);
  if (!res.ok) throw new Error('Failed to fetch groups');
  const data = await res.json();
  return data.groups;
}

export async function fetchReleases(group) {
  const res = await fetch(`${API_BASE}/api/releases?group=${encodeURIComponent(group)}`);
  if (!res.ok) throw new Error('Failed to fetch releases');
  const data = await res.json();
  return data.releases;
}

export async function postPredict(group) {
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

