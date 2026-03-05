import React from 'react';
import {useCurrentFrame} from 'remotion';
import {colors} from '../config/colors';
import type {TerminalLine} from '../config/terminalContent';

type ScrollingTerminalProps = {
  lines: TerminalLine[];
  startFrame?: number;
  frame?: number;
  charsPerFrame?: number;
  maxLines?: number;
  speedMultiplier?: number;
  style?: React.CSSProperties;
};

const splitPrefix = (line: string): {prefix: string | null; rest: string} => {
  const match = line.match(/^(\[[^\]]+\])\s?(.*)$/);
  if (!match) {
    return {prefix: null, rest: line};
  }

  return {
    prefix: match[1],
    rest: match[2],
  };
};

const getPrefixColor = (prefix: string | null): string => {
  if (!prefix) {
    return colors.terminalText;
  }

  if (prefix === '[agent]') {
    return colors.terminalGreen;
  }

  if (prefix === '[worker]') {
    return colors.terminalYellow;
  }

  if (prefix === '[backtest]' || prefix === '[ws]') {
    return colors.terminalCyan;
  }

  if (prefix === '[kalshi-api]' || prefix === '[exec]') {
    return colors.terminalRed;
  }

  return colors.terminalText;
};

export const ScrollingTerminal: React.FC<ScrollingTerminalProps> = ({
  lines,
  startFrame = 0,
  frame,
  charsPerFrame = 2,
  maxLines = 14,
  speedMultiplier = 1,
  style,
}) => {
  const localFrame = useCurrentFrame();
  const currentFrame = frame ?? localFrame;
  const progressedFrame = Math.max(0, currentFrame - startFrame);

  const visibleLines = lines
    .map((line) => {
      const rawElapsed = progressedFrame - line.delay;
      if (rawElapsed < 0) {
        return null;
      }

      const lineElapsed = rawElapsed * speedMultiplier;
      const localCharsPerFrame = line.charsPerFrame ?? charsPerFrame;
      const shownChars = Math.min(line.text.length, Math.floor(lineElapsed * localCharsPerFrame));
      if (shownChars <= 0) {
        return null;
      }

      return {
        ...line,
        visibleText: line.text.slice(0, shownChars),
      };
    })
    .filter((line): line is TerminalLine & {visibleText: string} => line !== null)
    .slice(-maxLines);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 7,
        ...style,
      }}
    >
      {visibleLines.map((line, idx) => {
        const {prefix, rest} = splitPrefix(line.visibleText);
        const danger = line.style === 'danger';
        return (
          <div
            key={`${line.text}-${idx}`}
            style={{
              fontSize: 15,
              lineHeight: 1.25,
              color: danger ? colors.terminalRed : colors.terminalText,
              fontWeight: danger ? 700 : 400,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              backgroundColor: danger ? 'rgba(243, 139, 168, 0.08)' : 'transparent',
              padding: danger ? '1px 4px' : 0,
              borderRadius: 4,
            }}
          >
            {prefix ? (
              <>
                <span style={{color: danger ? colors.terminalRed : getPrefixColor(prefix)}}>{prefix}</span>
                {rest ? ` ${rest}` : ''}
              </>
            ) : (
              line.visibleText
            )}
          </div>
        );
      })}
    </div>
  );
};
