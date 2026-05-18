import { fmt } from '@/lib/dateUtils';

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

export default function ReleaseModal({ release, onClose }) {
  if (!release) return null;
  const color = colorFor(release.type);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={e => e.stopPropagation()}>

        <div style={{ marginBottom: '14px' }}>
          <span className="modal-type-badge" style={{
            background: `${color}22`,
            border: `1px solid ${color}55`,
            color,
          }}>
            {release.type || 'Unknown'}
          </span>
        </div>

        <h3 className="modal-title">{release.title}</h3>
        <p className="modal-date">{fmt(new Date(release.date + 'T00:00:00'))}</p>

        <button
          className="modal-close-btn"
          onClick={onClose}
          onMouseEnter={e => { e.target.style.background = 'rgba(255,255,255,0.1)'; }}
          onMouseLeave={e => { e.target.style.background = 'rgba(255,255,255,0.06)'; }}
        >
          Close
        </button>
      </div>
    </div>
  );
}
