import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { fetchGroups } from '@/lib/api';
import Typing from '@/components/Typing';
import GenerationSection from '@/components/GenerationSection';

export default function Home() {
  const router = useRouter();
  const [groups, setGroups] = useState([]);
  const [error, setError]   = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [headerDone, setHeaderDone] = useState(false);

  useEffect(() => {
    fetchGroups()
      .then(gs => { setGroups(gs); setLoaded(true); })
      .catch(e => setError(e.message));
  }, []);

  const { fourthGen, fifthGen } = useMemo(() => ({
    fourthGen: groups.filter(g => g.generation === '4th Gen'),
    fifthGen:  groups.filter(g => g.generation === '5th Gen'),
  }), [groups]);

  const onPick = name => router.push(`/group?name=${encodeURIComponent(name)}`);

  return (
    <main className="page-container">

      {/* ── Header ── */}
      <div style={{ textAlign: 'center', marginBottom: '56px' }}>
        <Typing
          text="Welcome to Warith's K-pop Release Predictor"
          onComplete={() => setHeaderDone(true)}
        />
        <p
          className="subheading-reveal"
          style={{
            opacity: headerDone ? 1 : 0,
            transform: headerDone ? 'translateY(0)' : 'translateY(10px)',
          }}
        >
          Choose a Group
        </p>
      </div>

      {/* ── Loading ── */}
      {!loaded && !error && (
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-body)', fontSize: '14px' }}>
          Loading…
        </p>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="error-banner">{error}</div>
      )}

      {/* ── Group grid ── */}
      {loaded && groups.length > 0 && (
        <div style={{
          maxWidth: '820px',
          margin: '0 auto',
          display: 'grid',
          gridTemplateColumns: '1fr 1px 1fr',
          gap: '0 32px',
        }}>
          <GenerationSection label="4th Gen" groups={fourthGen} animationClass="fade-up" onPick={onPick} />

          <div style={{
            background: 'linear-gradient(to bottom, transparent 0%, rgba(255,255,255,0.08) 15%, rgba(255,255,255,0.08) 85%, transparent 100%)',
          }} />

          <GenerationSection label="5th Gen" groups={fifthGen} animationClass="fade-up fade-up-delay-1" onPick={onPick} />
        </div>
      )}
    </main>
  );
}
