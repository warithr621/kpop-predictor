import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { fetchGroups } from '@/lib/api';

export default function GroupCanvas() {
  const router = useRouter();
  const { gen } = router.query;
  const [groups, setGroups] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchGroups()
      .then((gs) => setGroups(gs))
      .catch((e) => setError(e.message));
  }, []);

  const filtered = useMemo(
    () => groups.filter((g) => (!gen ? true : g.generation === gen)),
    [groups, gen]
  );

  // Increased radius to create more space around the center
  const radius = 200;
  const center = { x: 300, y: 300 };

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-50 text-gray-800 p-6">
      <div className="relative" style={{ width: 600, height: 600 }}>
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="rounded-full w-32 h-32 bg-gradient-to-br from-purple-500 to-blue-500 text-white flex items-center justify-center text-center p-4 shadow-lg">
            <div>
              <div className="text-sm opacity-80">Generation</div>
              <div className="text-xl font-semibold">{gen || 'All'}</div>
            </div>
          </div>
        </div>
        {filtered.map((g, idx) => {
          const angle = (idx / filtered.length) * Math.PI * 2;
          const x = center.x + radius * Math.cos(angle) - 12;
          const y = center.y + radius * Math.sin(angle) - 12;
          return (
            <button
              key={g.name}
              onClick={() => router.push(`/group?name=${encodeURIComponent(g.name)}`)}
              className="absolute rounded-full w-6 h-6 bg-gradient-to-br from-purple-400 to-blue-400 hover:w-8 hover:h-8 hover:-translate-x-1 hover:-translate-y-1 transition-all duration-200 shadow-md hover:shadow-lg border-2 border-white hover:border-purple-300"
              style={{ left: x, top: y }}
              title={`${g.name} (${g.company || 'Unknown'})`}
            />
          );
        })}
        {error && (
          <div className="absolute bottom-2 left-2 right-2 text-red-500 text-sm bg-white p-2 rounded shadow">{error}</div>
        )}
      </div>
    </main>
  );
}

