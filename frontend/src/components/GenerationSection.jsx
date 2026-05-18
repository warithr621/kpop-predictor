export default function GenerationSection({ label, groups, animationClass, onPick }) {
  const gen = label.startsWith('4') ? '4th' : '5th';
  const badgeClass = `gen-badge-${gen}`;
  const cardClass  = `card-${gen}`;
  const displayLabel = label.replace(' Gen', ' Generation');

  return (
    <div className={animationClass}>
      <div style={{ marginBottom: '14px' }}>
        <span className={badgeClass}>{displayLabel}</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
        {groups.map(g => (
          <button key={g.name} className={cardClass} onClick={() => onPick(g.name)}>
            <div className="card-name">{g.name}</div>
            {g.company && <div className="card-company">{g.company}</div>}
          </button>
        ))}
      </div>
    </div>
  );
}
