import { useMemo, useState } from 'react';
import { toDate } from '@/lib/dateUtils';
import ReleaseModal from '@/components/ReleaseModal';

const SVG_WIDTH  = 820;
const SVG_HEIGHT = 80;
const SVG_PAD    = 20;

const TYPE_COLORS = {
  single: '#f0287a',
  ep:     '#22d3ee',
  album:  '#fbbf24',
};

function colorFor(type) {
  if (!type) return 'rgba(255,255,255,0.25)';
  const t = type.toLowerCase();
  if (t.includes('single')) return TYPE_COLORS.single;
  if (t.includes('ep'))     return TYPE_COLORS.ep;
  if (t.includes('album'))  return TYPE_COLORS.album;
  return 'rgba(255,255,255,0.25)';
}

const LEGEND_ITEMS = [
  ['Single', TYPE_COLORS.single],
  ['EP',     TYPE_COLORS.ep],
  ['Album',  TYPE_COLORS.album],
];

export default function Timeline({ releases = [] }) {
  const [selected, setSelected] = useState(null);

  const { minDate, maxDate, validReleases } = useMemo(() => {
    const valid = releases.filter(r => toDate(r.date));
    if (!valid.length) return { minDate: null, maxDate: null, validReleases: [] };
    const dates = valid.map(r => toDate(r.date));
    return {
      minDate: new Date(Math.min(...dates)),
      maxDate: new Date(Math.max(...dates)),
      validReleases: valid,
    };
  }, [releases]);

  if (!validReleases.length) {
    return (
      <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-body)', fontSize: '14px' }}>
        No release history found
      </div>
    );
  }

  const total = maxDate - minDate || 1;
  const xOf = d => SVG_PAD + ((toDate(d) - minDate) / total) * (SVG_WIDTH - SVG_PAD * 2);

  return (
    <div style={{ width: '100%' }}>
      <div style={{ overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          width="100%"
          style={{ display: 'block', minWidth: '480px' }}
        >
          {/* Axis line */}
          <line
            x1={SVG_PAD} x2={SVG_WIDTH - SVG_PAD}
            y1={SVG_HEIGHT / 2} y2={SVG_HEIGHT / 2}
            stroke="rgba(255,255,255,0.1)" strokeWidth="1"
          />

          {/* Release markers */}
          {validReleases.map((r, i) => {
            const cx = xOf(r.date);
            const c  = colorFor(r.type);
            return (
              <g key={i} style={{ cursor: 'pointer' }} onClick={() => setSelected(r)}>
                <line
                  x1={cx} x2={cx}
                  y1={SVG_HEIGHT / 2 - 14} y2={SVG_HEIGHT / 2 + 14}
                  stroke={c} strokeWidth="1" strokeOpacity="0.35"
                />
                <circle
                  cx={cx} cy={SVG_HEIGHT / 2} r={5}
                  fill={c}
                  style={{ filter: `drop-shadow(0 0 5px ${c}88)` }}
                />
                <circle cx={cx} cy={SVG_HEIGHT / 2} r={10} fill="transparent" />
              </g>
            );
          })}

          {/* Axis labels */}
          <text x={SVG_PAD} y={SVG_HEIGHT - 4} fill="rgba(255,255,255,0.5)" fontSize="11" fontFamily="Outfit, sans-serif">
            {minDate.toISOString().slice(0, 7)}
          </text>
          <text x={SVG_WIDTH - SVG_PAD} y={SVG_HEIGHT - 4} fill="rgba(255,255,255,0.5)" fontSize="11" fontFamily="Outfit, sans-serif" textAnchor="end">
            {maxDate.toISOString().slice(0, 7)}
          </text>
        </svg>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '20px', marginTop: '14px' }}>
        {LEGEND_ITEMS.map(([label, color]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span style={{
              display: 'inline-block', width: '8px', height: '8px',
              borderRadius: '50%', background: color,
              boxShadow: `0 0 6px ${color}88`,
            }} />
            <span style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)' }}>{label}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {validReleases.length} releases · click to view
        </div>
      </div>

      <ReleaseModal release={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
