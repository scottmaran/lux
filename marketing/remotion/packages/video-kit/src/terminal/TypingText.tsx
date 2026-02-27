import React from 'react';
import {useCurrentFrame} from 'remotion';
import {DEFAULT_TERMINAL_THEME, type TerminalTheme} from './theme';

export type TypingTextProps = {
  text: string;
  startFrame?: number;
  charsPerFrame?: number;
  frame?: number;
  blinkRate?: number;
  cursorChar?: string;
  style?: React.CSSProperties;
  theme?: Partial<TerminalTheme>;
};

export const TypingText: React.FC<TypingTextProps> = ({
  text,
  startFrame = 0,
  charsPerFrame = 2,
  frame,
  blinkRate = 30,
  cursorChar = '_',
  style,
  theme,
}) => {
  const localFrame = useCurrentFrame();
  const currentFrame = frame ?? localFrame;
  const elapsed = Math.max(0, currentFrame - startFrame);
  const shownChars = Math.min(text.length, Math.floor(elapsed * charsPerFrame));
  const typed = text.slice(0, shownChars);
  const done = shownChars >= text.length;
  const palette = {...DEFAULT_TERMINAL_THEME, ...theme};

  const cursorVisible = done ? Math.floor((currentFrame - startFrame) / blinkRate) % 2 === 0 : true;

  return (
    <span style={style}>
      {typed}
      <span
        style={{
          color: palette.terminalCursor,
          opacity: cursorVisible ? 1 : 0,
        }}
      >
        {cursorChar}
      </span>
    </span>
  );
};
