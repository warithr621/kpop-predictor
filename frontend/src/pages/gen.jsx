import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { fetchGroups } from '@/lib/api';

function GroupBubble({ group, onClick, side }) {
  const bg = side === 'left'
    ? 'linear-gradient(135deg, #c084fc 0%, #a855f7 60%, #9333ea 100%)'
    : 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 60%, #2563eb 100%)';

  return (
    <button
      onClick={onClick}
      className="w-full rounded-2xl px-5 py-3.5 text-left text-white shadow-md hover:shadow-xl hover:scale-105 active:scale-100 transition-all duration-200"
      style={{ background: bg }}
    >
      <div className="font-semibold text-sm leading-snug">{group.name}</div>
      {group.company && (
        <div className="text-xs mt-0.5" style={{ opacity: 0.72 }}>{group.company}</div>
      )}
    </button>
  );
}

function GenColumn({ label, groups, onPick, side }) {
  const headerBg = side === 'left'
    ? 'linear-gradient(135deg, #a855f7, #7c3aed)'
    : 'linear-gradient(135deg, #3b82f6, #1d4ed8)';
  const glowColor = side === 'left' ? 'rgba(168,85,247,0.15)' : 'rgba(59,130,246,0.15)';

  return (
    <div className="flex-1 flex flex-col gap-4">
      <div className="flex justify-center">
        <span
          className="inline-block px-8 py-2.5 rounded-full text-white font-bold text-lg tracking-wide shadow-lg"
          style={{ background: headerBg }}
        >
          {label}
        </span>
      </div>

      <div
        className="rounded-3xl p-4 flex flex-col gap-2.5"
        style={{ background: glowColor, backdropFilter: 'blur(4px)' }}
      >
        {groups.map(group => (
          <GroupBubble
            key={group.name}
            group={group}
            onClick={() => onPick(group.name)}
            side={side}
          />
        ))}
      </div>
    </div>
  );
}

export default function GenChooser() {
  const router = useRouter();
  const [groups, setGroups] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchGroups()
      .then(setGroups)
      .catch((e) => setError(e.message));
  }, []);

  const { fourthGen, fifthGen } = useMemo(() => ({
    fourthGen: groups.filter(g => g.generation === '4th Gen'),
    fifthGen:  groups.filter(g => g.generation === '5th Gen'),
  }), [groups]);

  const onPick = (name) => router.push(`/group?name=${encodeURIComponent(name)}`);

  return (
    <main
      className="min-h-screen text-gray-800 px-8 py-10"
      style={{ background: 'linear-gradient(135deg, #f5f3ff 0%, #eff6ff 55%, #eef2ff 100%)' }}
    >
      <h1 className="text-center text-3xl font-bold text-gray-700 mb-8 tracking-tight">
        Choose a Group
      </h1>

      {groups.length === 0 && !error && (
        <p className="text-center text-gray-400 text-lg mt-20">Loading groups…</p>
      )}

      {error && (
        <div className="max-w-md mx-auto mt-6 text-red-500 text-sm bg-white p-3 rounded-xl shadow">
          {error}
        </div>
      )}

      {groups.length > 0 && (
        <div className="max-w-3xl mx-auto flex gap-6">
          <GenColumn label="4th Gen" groups={fourthGen} onPick={onPick} side="left" />

          <div className="w-px self-stretch rounded-full my-2" style={{ background: 'linear-gradient(to bottom, transparent, #c4b5fd, transparent)' }} />

          <GenColumn label="5th Gen" groups={fifthGen} onPick={onPick} side="right" />
        </div>
      )}
    </main>
  );
}
