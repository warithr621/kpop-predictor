import { useRouter } from 'next/router';
import { useEffect, useMemo, useState } from 'react';
import { fetchGroups } from '@/lib/api';

const GenCircle = ({ label, side, x, y }) => (
  <div
    className={`absolute rounded-full w-32 h-32 flex items-center justify-center text-lg font-semibold text-white shadow-lg z-20 ${
      side === 'left' 
        ? 'bg-gradient-to-br from-purple-500 to-purple-700' 
        : 'bg-gradient-to-br from-blue-500 to-blue-700'
    }`}
    style={{ left: x - 64, top: y - 64 }}
  >
    {label}
  </div>
);

const GroupCircle = ({ group, onClick, side, x, y }) => (
  <button
    onClick={onClick}
    className={`absolute rounded-full w-24 h-24 flex items-center justify-center text-white shadow-md hover:shadow-lg transition-all duration-200 hover:scale-110 z-10 ${
      side === 'left'
        ? 'bg-gradient-to-br from-purple-300 to-purple-500 hover:from-purple-400 hover:to-purple-600'
        : 'bg-gradient-to-br from-blue-300 to-blue-500 hover:from-blue-400 hover:to-blue-600'
    }`}
    style={{ left: x - 48, top: y - 48 }}
    title={`${group.name} (${group.company || 'Unknown'})`}
  >
    <span className="text-center text-xs font-medium leading-tight px-2 break-words hyphens-auto overflow-hidden">
      {group.name}
    </span>
  </button>
);

const ConnectingLine = ({ fromX, fromY, toX, toY, side }) => (
  <line
    x1={fromX}
    y1={fromY}
    x2={toX}
    y2={toY}
    stroke={side === 'left' ? '#a855f7' : '#3b82f6'}
    strokeWidth="2"
    opacity="0.6"
    className="z-0"
  />
);

export default function GenChooser() {
  const router = useRouter();
  const [groups, setGroups] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchGroups()
      .then((gs) => setGroups(gs))
      .catch((e) => setError(e.message));
  }, []);

  const { fourthGen, fifthGen } = useMemo(() => {
    const fourth = groups.filter(g => g.generation === '4th Gen');
    const fifth = groups.filter(g => g.generation === '5th Gen');
    return { fourthGen: fourth, fifthGen: fifth };
  }, [groups]);

  const onPickGroup = (groupName) => {
    router.push(`/group?name=${encodeURIComponent(groupName)}`);
  };

  // Canvas dimensions and centers for each generation - much more spread out
  const canvasWidth = 1400;
  const canvasHeight = 800;
  const leftCenter = { x: 350, y: 400 };
  const rightCenter = { x: 1050, y: 400 };
  const groupRadius = 300; // Increased radius for more spread

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-50 via-blue-50 to-indigo-50 text-gray-800 p-6 overflow-hidden">
      <div className="relative" style={{ width: canvasWidth, height: canvasHeight }}>
        {/* SVG for connecting lines */}
        <svg className="absolute inset-0 w-full h-full" style={{ zIndex: 0 }}>
          {/* 4th Gen connecting lines */}
          {fourthGen.map((group, idx) => {
            const angle = (idx / fourthGen.length) * Math.PI * 2;
            const groupX = leftCenter.x + groupRadius * Math.cos(angle);
            const groupY = leftCenter.y + groupRadius * Math.sin(angle);
            return (
              <ConnectingLine
                key={`line-4th-${group.name}`}
                fromX={leftCenter.x}
                fromY={leftCenter.y}
                toX={groupX}
                toY={groupY}
                side="left"
              />
            );
          })}
          
          {/* 5th Gen connecting lines */}
          {fifthGen.map((group, idx) => {
            const angle = (idx / fifthGen.length) * Math.PI * 2;
            const groupX = rightCenter.x + groupRadius * Math.cos(angle);
            const groupY = rightCenter.y + groupRadius * Math.sin(angle);
            return (
              <ConnectingLine
                key={`line-5th-${group.name}`}
                fromX={rightCenter.x}
                fromY={rightCenter.y}
                toX={groupX}
                toY={groupY}
                side="right"
              />
            );
          })}
        </svg>

        {/* 4th Gen Circle */}
        <GenCircle label="4th Gen" side="left" x={leftCenter.x} y={leftCenter.y} />
        
        {/* 5th Gen Circle */}
        <GenCircle label="5th Gen" side="right" x={rightCenter.x} y={rightCenter.y} />

        {/* 4th Gen Groups */}
        {fourthGen.map((group, idx) => {
          const angle = (idx / fourthGen.length) * Math.PI * 2;
          const x = leftCenter.x + groupRadius * Math.cos(angle);
          const y = leftCenter.y + groupRadius * Math.sin(angle);
          return (
            <GroupCircle
              key={group.name}
              group={group}
              onClick={() => onPickGroup(group.name)}
              side="left"
              x={x}
              y={y}
            />
          );
        })}

        {/* 5th Gen Groups */}
        {fifthGen.map((group, idx) => {
          const angle = (idx / fifthGen.length) * Math.PI * 2;
          const x = rightCenter.x + groupRadius * Math.cos(angle);
          const y = rightCenter.y + groupRadius * Math.sin(angle);
          return (
            <GroupCircle
              key={group.name}
              group={group}
              onClick={() => onPickGroup(group.name)}
              side="right"
              x={x}
              y={y}
            />
          );
        })}

        {error && (
          <div className="absolute bottom-4 left-4 right-4 text-red-500 text-sm bg-white p-3 rounded shadow-lg z-30">
            {error}
          </div>
        )}

        {groups.length === 0 && !error && (
          <div className="absolute inset-0 flex items-center justify-center z-30">
            <div className="text-gray-500">Loading groups...</div>
          </div>
        )}
      </div>
    </main>
  );
}

