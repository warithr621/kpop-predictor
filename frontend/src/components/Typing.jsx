import { useEffect, useState } from 'react';

export default function Typing({ text, speed = 40 }) {
  const [display, setDisplay] = useState('');
  
  useEffect(() => {
    setDisplay('');
    let i = 0;
    const id = setInterval(() => {
      if (i < text.length) {
        setDisplay(text.slice(0, i + 1));
        i += 1;
      } else {
        clearInterval(id);
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);
  
  return (
    <span className="typing-container fade-caret text-3xl sm:text-5xl font-semibold tracking-tight">
      {display}
    </span>
  );
}

