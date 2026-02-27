import React from 'react';
import {useCurrentFrame} from 'remotion';
import {colors} from '../config/colors';

type TypingTextProps = {
  text: string;
  startFrame?: number;
  charsPerFrame?: number;
  frame?: number;
  blinkRate?: number;
  cursorChar?: string;
  style?: React.CSSProperties;
};

export const TypingText: React.FC<TypingTextProps> = ({
  text,
  startFrame = 0,
  charsPerFrame = 2,
  frame,
  blinkRate = 30,
  cursorChar = '_',
  style,
}) => {
  const localFrame = useCurrentFrame();
  const currentFrame = frame ?? localFrame;
  const elapsed = Math.max(0, currentFrame - startFrame);
  const shownChars = Math.min(text.length, Math.floor(elapsed * charsPerFrame));
  const typed = text.slice(0, shownChars);
  const done = shownChars >= text.length;

  const cursorVisible = done
    ? Math.floor((currentFrame - startFrame) / blinkRate) % 2 === 0
    : true;

  return (
    <span style={style}>
      {typed}
      <span
        style={{
          color: colors.terminalCursor,
          opacity: cursorVisible ? 1 : 0,
        }}
      >
        {cursorChar}
      </span>
    </span>
  );
};
