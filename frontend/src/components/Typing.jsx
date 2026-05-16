import { useEffect, useState } from 'react';

export default function Typing({ text, speed = 42, onComplete, size = 'lg' }) {
  const [display, setDisplay] = useState('');
  const [done, setDone] = useState(false);

  const sizeStyle = {
    lg: { fontSize: 'clamp(1.55rem, 3.5vw, 2.85rem)' },
    md: { fontSize: 'clamp(1.2rem, 2.5vw, 1.8rem)' },
  }[size] || { fontSize: 'clamp(1.55rem, 3.5vw, 2.85rem)' };

  useEffect(() => {
    setDisplay('');
    setDone(false);
    let i = 0;
    const id = setInterval(() => {
      if (i < text.length) {
        setDisplay(text.slice(0, i + 1));
        i++;
      } else {
        clearInterval(id);
        setDone(true);
        onComplete?.();
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);

  return (
    <span
      className={`typing-container ${done ? 'typing-cursor-done' : 'typing-cursor-blink'}`}
      style={sizeStyle}
    >
      {display}
    </span>
  );
}
