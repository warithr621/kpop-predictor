import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { fetchGroups, fetchReleases, postPredict } from '@/lib/api';
import Timeline from '@/components/Timeline';

function PredictionCard({ result, accentColor, glowColor }) {
  // API returns ISO datetime strings ("2026-05-17T00:00:00") — slice to date only
  // before parsing to avoid "Invalid Date" from double T suffix
  const parseDate = s => new Date(s.slice(0, 10) + 'T12:00:00');
  const low  = parseDate(result.pred_date_low);
  const med  = parseDate(result.pred_date_med);
  const high = parseDate(result.pred_date_high);

  const fmt = d =>
    d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  const fmtShort = d =>
    d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

  const total = high - low || 1;
  const medPct = Math.max(0, Math.min(100, ((med - low) / total) * 100));

  const today = new Date();
  const daysFromNow = Math.round((med - today) / 86400000);
  const daysLabel = daysFromNow > 0
    ? `${daysFromNow} day${daysFromNow !== 1 ? 's' : ''} from today`
    : daysFromNow === 0
    ? 'Today'
    : `${Math.abs(daysFromNow)} days ago`;

  return (
    <div className="pred-card fade-up">
      <div className="pred-label">Next Predicted Release</div>

      <div style={{ marginBottom: '28px' }}>
        <div className="pred-date-hero">{fmt(med)}</div>
        <div className="pred-date-sub">{daysLabel}</div>
      </div>

      {/* Range bar */}
      <div style={{ position: 'relative', marginBottom: '10px' }}>
        <div style={{
          height: '3px',
          background: 'rgba(255,255,255,0.13)',
          borderRadius: '2px',
          position: 'relative',
        }}>
          <div style={{
            position: 'absolute',
            left: 0, right: 0, top: 0, bottom: 0,
            background: `linear-gradient(to right, rgba(255,255,255,0.12), ${accentColor}55, rgba(255,255,255,0.12))`,
            borderRadius: '2px',
          }} />
          {/* Low dot */}
          <div style={{
            position: 'absolute', left: '0%', top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '10px', height: '10px', borderRadius: '50%',
            background: 'rgba(255,255,255,0.4)',
            border: '2px solid rgba(255,255,255,0.7)',
          }} />
          {/* Med dot */}
          <div style={{
            position: 'absolute', left: `${medPct}%`, top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '14px', height: '14px', borderRadius: '50%',
            background: accentColor,
            boxShadow: `0 0 12px ${glowColor}`,
          }} />
          {/* High dot */}
          <div style={{
            position: 'absolute', left: '100%', top: '50%',
            transform: 'translate(-50%, -50%)',
            width: '10px', height: '10px', borderRadius: '50%',
            background: 'rgba(255,255,255,0.4)',
            border: '2px solid rgba(255,255,255,0.7)',
          }} />
        </div>
      </div>

      {/* Date labels */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>{fmtShort(low)}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>Optimistic</div>
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: accentColor, fontWeight: 600 }}>{fmtShort(med)}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>Most Likely</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 500 }}>{fmtShort(high)}</div>
          <div style={{ fontFamily: 'var(--font-body)', fontSize: '12px', color: 'var(--text-muted)', marginTop: '3px' }}>Late estimate</div>
        </div>
      </div>

      {/* Info note */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '9px',
        padding: '11px 14px',
        borderRadius: '9px',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
      }}>
        <span style={{ fontSize: '13px', color: 'var(--text-muted)', flexShrink: 0, lineHeight: '20px' }}>ⓘ</span>
        <span style={{ flex: 1, fontFamily: 'var(--font-body)', fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.6, textAlign: 'center' }}>
          <strong style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Optimistic</strong> is the p10 estimate: only 10% of comparable groups release this quickly. <br />
          <strong style={{ color: accentColor, fontWeight: 600 }}>Most Likely</strong> is the p50 median estimate. <br />
          <strong style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Late estimate</strong> is the p90 estimate: 90% of comparable groups have released by this date.
        </span>
      </div>
    </div>
  );
}

export default function GroupPage() {
  const router = useRouter();
  const { name } = router.query;
  const [meta, setMeta]       = useState(null);
  const [releases, setReleases] = useState([]);
  const [loading, setLoading]  = useState(false);
  const [error, setError]      = useState(null);
  const [result, setResult]    = useState(null);

  useEffect(() => {
    if (!name) return;
    fetchGroups().then(gs => {
      setMeta(gs.find(g => g.name === name) || { name });
    });
    fetchReleases(name).then(setReleases).catch(e => setError(e.message));
  }, [name]);

  const accentColor = meta?.generation === '4th Gen' ? '#f0287a' : '#22d3ee';
  const glowColor   = meta?.generation === '4th Gen'
    ? 'rgba(240, 40, 122, 0.4)'
    : 'rgba(34, 211, 238, 0.4)';
  const badgeClass  = meta?.generation === '4th Gen' ? 'gen-badge-4th' : 'gen-badge-5th';

  const onPredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await postPredict(name));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={{ minHeight: '100vh', padding: '40px 24px 80px' }}>
      <div style={{ maxWidth: '860px', margin: '0 auto' }}>

        {/* ── Top bar ── */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '36px' }}>
          <button className="back-btn" onClick={() => router.push('/')}>
            <span>←</span> Groups
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {meta?.generation && <span className={badgeClass}>{meta.generation}</span>}
            {meta?.company && (
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: '13px',
                color: 'var(--text-secondary)',
              }}>
                {meta.company}
              </span>
            )}
          </div>
        </div>

        {/* ── Group name ── */}
        <div style={{ marginBottom: '36px' }} className="fade-up">
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: 'clamp(2.2rem, 5vw, 3.8rem)',
            letterSpacing: '-0.04em',
            lineHeight: 1,
            color: 'var(--text-primary)',
            margin: 0,
          }}>
            {meta?.name || name}
          </h1>
        </div>

        {/* ── Timeline section ── */}
        <div style={{ marginBottom: '32px' }} className="fade-up fade-up-delay-1">
          <div style={{
            fontFamily: 'var(--font-body)',
            fontSize: '12px',
            fontWeight: 600,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--text-secondary)',
            marginBottom: '14px',
          }}>
            Release History
          </div>
          <div style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.09)',
            borderRadius: '14px',
            padding: '20px 24px',
          }}>
            <Timeline releases={releases} accentColor={accentColor} />
          </div>
        </div>

        <hr className="section-divider" />

        {/* ── Predict button ── */}
        <div style={{ marginBottom: '24px' }} className="fade-up fade-up-delay-2">
          <button
            className="predict-btn"
            onClick={onPredict}
            disabled={loading}
            onMouseEnter={e => { e.currentTarget.style.boxShadow = `0 8px 30px ${glowColor}`; }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'none'; }}
            style={{
              background: `linear-gradient(135deg, ${accentColor}, ${
                meta?.generation === '4th Gen' ? '#c026d3' : '#6366f1'
              })`,
            }}
          >
            {loading
              ? 'Predicting…'
              : `Predict ${meta?.name || ''}'s next release`}
          </button>

          {error && (
            <div style={{
              marginTop: '14px',
              padding: '10px 16px',
              borderRadius: '10px',
              background: 'rgba(255,60,60,0.08)',
              border: '1px solid rgba(255,60,60,0.2)',
              color: '#ff7070',
              fontFamily: 'var(--font-body)',
              fontSize: '13px',
            }}>
              {error}
            </div>
          )}
        </div>

        {/* ── Prediction result ── */}
        {result && (
          <PredictionCard
            result={result}
            accentColor={accentColor}
            glowColor={glowColor}
          />
        )}
      </div>
    </main>
  );
}
