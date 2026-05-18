import { fmt, fmtShort, daysFromNow, parseISODate } from '@/lib/dateUtils';

export default function PredictionCard({ result, accentColor, glowColor }) {
  const low  = parseISODate(result.pred_date_low);
  const med  = parseISODate(result.pred_date_med);
  const high = parseISODate(result.pred_date_high);

  const total  = high - low || 1;
  const medPct = Math.max(0, Math.min(100, ((med - low) / total) * 100));

  const days      = daysFromNow(med);
  const daysLabel = days > 0
    ? `${days} day${days !== 1 ? 's' : ''} from today`
    : days === 0 ? 'Today'
    : `${Math.abs(days)} days ago`;

  return (
    <div className="pred-card fade-up">
      <div className="pred-label">Next Predicted Release</div>

      <div style={{ marginBottom: '28px' }}>
        <div className="pred-date-hero">{fmt(med)}</div>
        <div className="pred-date-sub">{daysLabel}</div>
      </div>

      {/* Range bar */}
      <div className="range-bar">
        <div className="range-bar__track">
          <div className="range-bar__gradient" style={{
            background: `linear-gradient(to right, rgba(255,255,255,0.12), ${accentColor}55, rgba(255,255,255,0.12))`,
          }} />
          <div className="range-bar__dot range-bar__dot--edge" style={{ left: '0%' }} />
          <div className="range-bar__dot range-bar__dot--med" style={{
            left: `${medPct}%`,
            background: accentColor,
            boxShadow: `0 0 12px ${glowColor}`,
          }} />
          <div className="range-bar__dot range-bar__dot--edge" style={{ left: '100%' }} />
        </div>
      </div>

      {/* Date labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <div className="range-label">{fmtShort(low)}</div>
          <div className="range-sublabel">Optimistic</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div className="range-label" style={{ color: accentColor, fontWeight: 600 }}>{fmtShort(med)}</div>
          <div className="range-sublabel">Most Likely</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="range-label">{fmtShort(high)}</div>
          <div className="range-sublabel">Late estimate</div>
        </div>
      </div>

      {/* Info note */}
      <div className="pred-info-note">
        <span className="pred-info-icon">ⓘ</span>
        <span className="pred-info-text">
          <strong style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Optimistic</strong> is the p25 estimate: only 25% of comparable groups release this quickly.{' '}
          <strong style={{ color: accentColor, fontWeight: 600 }}>Most Likely</strong> is the p50 median estimate.{' '}
          <strong style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Late estimate</strong> is the p75 estimate: 75% of comparable groups have released by this date.
        </span>
      </div>
    </div>
  );
}
