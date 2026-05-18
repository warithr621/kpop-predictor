import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { fetchGroups, fetchReleases, predictNextRelease } from '@/lib/api';
import { getAccentColor, getGlowColor, getGradientEnd, getBadgeClass } from '@/lib/themeUtils';
import Timeline from '@/components/Timeline';
import PredictionCard from '@/components/PredictionCard';

export default function GroupPage() {
  const router = useRouter();
  const { name } = router.query;
  const [meta, setMeta]         = useState(null);
  const [releases, setReleases] = useState([]);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState(null);
  const [result, setResult]     = useState(null);

  useEffect(() => {
    if (!name) return;
    fetchGroups().then(gs => setMeta(gs.find(g => g.name === name) || { name }));
    fetchReleases(name).then(setReleases).catch(e => setError(e.message));
  }, [name]);

  const generation  = meta?.generation;
  const accentColor = getAccentColor(generation);
  const glowColor   = getGlowColor(generation);
  const badgeClass  = getBadgeClass(generation);

  const onPredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await predictNextRelease(name));
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
            {generation && <span className={badgeClass}>{generation}</span>}
            {meta?.company && (
              <span style={{ fontFamily: 'var(--font-body)', fontSize: '13px', color: 'var(--text-secondary)' }}>
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
            style={{ background: `linear-gradient(135deg, ${accentColor}, ${getGradientEnd(generation)})` }}
          >
            {loading ? 'Predicting…' : `Predict ${meta?.name || ''}'s next release`}
          </button>

          {error && (
            <div className="error-banner" style={{ marginTop: '14px', fontSize: '13px' }}>
              {error}
            </div>
          )}
        </div>

        {/* ── Prediction result ── */}
        {result && (
          <PredictionCard result={result} accentColor={accentColor} glowColor={glowColor} />
        )}

      </div>
    </main>
  );
}
