import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { fetchGroups } from '@/lib/api';
import Typing from '@/components/Typing';

export default function Home() {
  const router = useRouter();
  const [groups, setGroups]     = useState([]);
  const [error, setError]       = useState(null);
  const [loaded, setLoaded]     = useState(false);
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
    <main style={{ minHeight: '100vh', paddingTop: '64px', paddingBottom: '80px', paddingLeft: '24px', paddingRight: '24px' }}>

      {/* ── Header ── */}
      <div style={{ textAlign: 'center', marginBottom: '56px' }}>
        <div>
          <Typing
            text="Welcome to Warith's K-pop Release Predictor"
            onComplete={() => setHeaderDone(true)}
          />
        </div>
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
        <div style={{
          maxWidth: '420px',
          margin: '0 auto',
          padding: '12px 16px',
          borderRadius: '10px',
          background: 'rgba(255,60,60,0.08)',
          border: '1px solid rgba(255,60,60,0.2)',
          color: '#ff7070',
          fontFamily: 'var(--font-body)',
          fontSize: '14px',
        }}>
          {error}
        </div>
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

          {/* 4th Gen */}
          <div className="fade-up">
            <div style={{ marginBottom: '14px' }}>
              <span className="gen-badge-4th">4th Generation</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
              {fourthGen.map(g => (
                <button
                  key={g.name}
                  className="card-4th"
                  onClick={() => onPick(g.name)}
                >
                  <div className="card-name">{g.name}</div>
                  {g.company && <div className="card-company">{g.company}</div>}
                </button>
              ))}
            </div>
          </div>

          {/* Divider */}
          <div style={{
            background: 'linear-gradient(to bottom, transparent 0%, rgba(255,255,255,0.08) 15%, rgba(255,255,255,0.08) 85%, transparent 100%)',
          }} />

          {/* 5th Gen */}
          <div className="fade-up fade-up-delay-1">
            <div style={{ marginBottom: '14px' }}>
              <span className="gen-badge-5th">5th Generation</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
              {fifthGen.map(g => (
                <button
                  key={g.name}
                  className="card-5th"
                  onClick={() => onPick(g.name)}
                >
                  <div className="card-name">{g.name}</div>
                  {g.company && <div className="card-company">{g.company}</div>}
                </button>
              ))}
            </div>
          </div>

        </div>
      )}
    </main>
  );
}
