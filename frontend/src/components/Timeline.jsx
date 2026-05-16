import { useMemo, useState } from 'react';

function toDate(d) {
  const dt = new Date(d);
  return isNaN(dt.getTime()) ? null : dt;
}

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

export default function Timeline({ releases = [], accentColor }) {
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

  if (!minDate || !maxDate || !validReleases.length) {
    return (
      <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-body)', fontSize: '14px' }}>
        No release history found
      </div>
    );
  }

  const W = 820;
  const H = 80;
  const PAD = 20;
  const total = maxDate - minDate || 1;
  const xOf = d => PAD + ((toDate(d) - minDate) / total) * (W - PAD * 2);

  const fmtDate = d => new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <div style={{ width: '100%' }}>
      <div style={{ overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          style={{ display: 'block', minWidth: '480px' }}
        >
          {/* Axis line */}
          <line
            x1={PAD} x2={W - PAD}
            y1={H / 2} y2={H / 2}
            stroke="rgba(255,255,255,0.1)"
            strokeWidth="1"
          />

          {/* Release markers */}
          {validReleases.map((r, i) => {
            const cx = xOf(r.date);
            const c  = colorFor(r.type);
            return (
              <g key={i} style={{ cursor: 'pointer' }} onClick={() => setSelected(r)}>
                {/* Vertical tick */}
                <line
                  x1={cx} x2={cx}
                  y1={H / 2 - 14} y2={H / 2 + 14}
                  stroke={c}
                  strokeWidth="1"
                  strokeOpacity="0.35"
                />
                {/* Dot */}
                <circle
                  cx={cx}
                  cy={H / 2}
                  r={5}
                  fill={c}
                  style={{ filter: `drop-shadow(0 0 5px ${c}88)` }}
                />
                {/* Hover ring (invisible, larger hit target) */}
                <circle cx={cx} cy={H / 2} r={10} fill="transparent" />
              </g>
            );
          })}

          {/* Axis labels */}
          <text x={PAD} y={H - 4} fill="rgba(255,255,255,0.5)" fontSize="11" fontFamily="Outfit, sans-serif">
            {minDate.toISOString().slice(0, 7)}
          </text>
          <text x={W - PAD} y={H - 4} fill="rgba(255,255,255,0.5)" fontSize="11" fontFamily="Outfit, sans-serif" textAnchor="end">
            {maxDate.toISOString().slice(0, 7)}
          </text>
        </svg>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '20px', marginTop: '14px' }}>
        {[['Single', TYPE_COLORS.single], ['EP', TYPE_COLORS.ep], ['Album', TYPE_COLORS.album]].map(([label, color]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <span style={{
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: color,
              boxShadow: `0 0 6px ${color}88`,
            }} />
            <span style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)' }}>{label}</span>
          </div>
        ))}
        <div style={{ marginLeft: 'auto', fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)' }}>
          {validReleases.length} releases · click to view
        </div>
      </div>

      {/* Release detail modal */}
      {selected && (
        <div
          onClick={() => setSelected(null)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            zIndex: 50,
          }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              background: '#0e0e28',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '16px',
              padding: '28px 32px',
              maxWidth: '380px',
              width: '100%',
              boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
            }}
          >
            {/* Type badge */}
            <div style={{ marginBottom: '14px' }}>
              <span style={{
                background: `${colorFor(selected.type)}22`,
                border: `1px solid ${colorFor(selected.type)}55`,
                color: colorFor(selected.type),
                fontFamily: 'var(--font-display)',
                fontSize: '10px',
                fontWeight: 700,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                padding: '4px 10px',
                borderRadius: '6px',
                display: 'inline-block',
              }}>
                {selected.type || 'Unknown'}
              </span>
            </div>

            <h3 style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: '20px',
              color: 'var(--text-primary)',
              margin: '0 0 8px',
              letterSpacing: '-0.02em',
            }}>
              {selected.title}
            </h3>
            <p style={{
              fontFamily: 'var(--font-body)',
              fontSize: '13px',
              color: 'var(--text-muted)',
              margin: 0,
            }}>
              {fmtDate(selected.date)}
            </p>

            <button
              onClick={() => setSelected(null)}
              style={{
                marginTop: '24px',
                fontFamily: 'var(--font-body)',
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--text-secondary)',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                padding: '8px 18px',
                cursor: 'pointer',
                transition: 'background 0.15s ease',
              }}
              onMouseEnter={e => e.target.style.background = 'rgba(255,255,255,0.1)'}
              onMouseLeave={e => e.target.style.background = 'rgba(255,255,255,0.06)'}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
