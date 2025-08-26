import { useMemo, useState } from 'react';

function toDate(d) {
  const date = new Date(d);
  return isNaN(date.getTime()) ? null : date;
}

export default function Timeline({ releases = [] }) {
  const [selectedRelease, setSelectedRelease] = useState(null);

  const { minDate, maxDate, validReleases } = useMemo(() => {
    const valid = releases.filter(r => {
      const date = toDate(r.date);
      return date !== null;
    });
    
    if (valid.length === 0) {
      return { minDate: null, maxDate: null, validReleases: [] };
    }
    
    const dates = valid.map(r => toDate(r.date));
    const min = new Date(Math.min(...dates));
    const max = new Date(Math.max(...dates));
    return { minDate: min, maxDate: max, validReleases: valid };
  }, [releases]);

  if (!minDate || !maxDate || validReleases.length === 0) {
    return (
      <div className="w-full text-center py-8 text-gray-500">
        No valid release dates found
      </div>
    );
  }

  const width = 900;
  const height = 120;
  const padding = 40;
  const total = maxDate - minDate || 1;
  const x = (d) => padding + ((toDate(d) - minDate) / total) * (width - padding * 2);

  const colorFor = (type) => {
    if (!type) return '#e5e7eb';
    const t = type.toLowerCase();
    if (t.includes('single')) return '#60a5fa';
    if (t.includes('ep')) return '#34d399';
    if (t.includes('album')) return '#f59e0b';
    return '#9ca3af';
  };

  return (
    <div className="w-full overflow-x-auto relative">
      <svg width={width} height={height} className="min-w-full">
        <line x1={padding} x2={width - padding} y1={height / 2} y2={height / 2} stroke="#374151" />
        {validReleases.map((r, i) => (
          <g key={i}>
            <line x1={x(r.date)} x2={x(r.date)} y1={height / 2 - 30} y2={height / 2 + 30} stroke={colorFor(r.type)} />
            <circle 
              cx={x(r.date)} 
              cy={height / 2} 
              r={6} 
              fill={colorFor(r.type)} 
              className="cursor-pointer hover:r-8 transition-all"
              onClick={() => setSelectedRelease(r)}
              style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.1))' }}
            />
          </g>
        ))}
        <text x={padding} y={height - 10} fill="#9ca3af" fontSize="10">{minDate.toISOString().slice(0, 10)}</text>
        <text x={width - padding - 70} y={height - 10} fill="#9ca3af" fontSize="10">{maxDate.toISOString().slice(0, 10)}</text>
      </svg>
      <div className="flex gap-4 text-sm text-gray-300 mt-2">
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full" style={{ background: '#60a5fa' }}></span> Single</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full" style={{ background: '#34d399' }}></span> EP</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full" style={{ background: '#f59e0b' }}></span> Album</div>
      </div>

      {selectedRelease && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg p-6 max-w-sm w-full shadow-xl">
            <h3 className="text-xl font-semibold mb-4 text-gray-800">{selectedRelease.title}</h3>
            <div className="space-y-2 mb-4">
              <div className="flex justify-between">
                <span className="text-gray-600">Release Date:</span>
                <span className="font-medium">{new Date(selectedRelease.date).toLocaleDateString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Type:</span>
                <span 
                  className="px-2 py-1 rounded-full text-sm text-white font-medium"
                  style={{ backgroundColor: colorFor(selectedRelease.type) }}
                >
                  {selectedRelease.type || 'Unknown'}
                </span>
              </div>
            </div>
            <div className="flex justify-end">
              <button
                className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600 transition"
                onClick={() => setSelectedRelease(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

