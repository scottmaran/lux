import React from 'react';
import {useCurrentFrame} from 'remotion';
import {DEFAULT_TERMINAL_THEME, type TerminalTheme} from './theme';
import type {TerminalLine, TerminalPrefixColorMap} from './types';

export type ScrollingTerminalProps = {
  lines: TerminalLine[];
  startFrame?: number;
  frame?: number;
  charsPerFrame?: number;
  maxLines?: number;
  speedMultiplier?: number;
  style?: React.CSSProperties;
  theme?: Partial<TerminalTheme>;
  prefixColorMap?: TerminalPrefixColorMap;
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

export const ScrollingTerminal: React.FC<ScrollingTerminalProps> = ({
  lines,
  startFrame = 0,
  frame,
  charsPerFrame = 2,
  maxLines = 14,
  speedMultiplier = 1,
  style,
  theme,
  prefixColorMap,
}) => {
  const localFrame = useCurrentFrame();
  const currentFrame = frame ?? localFrame;
  const progressedFrame = Math.max(0, currentFrame - startFrame);
  const palette = {...DEFAULT_TERMINAL_THEME, ...theme};

  const colors: TerminalPrefixColorMap = {
    '[agent]': palette.terminalGreen,
    '[worker]': palette.terminalYellow,
    '[backtest]': palette.terminalCyan,
    '[ws]': palette.terminalCyan,
    '[kalshi-api]': palette.terminalRed,
    '[exec]': palette.terminalRed,
    ...prefixColorMap,
  };

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
        const prefixColor = prefix ? colors[prefix] ?? palette.terminalText : palette.terminalText;

        return (
          <div
            key={`${line.text}-${idx}`}
            style={{
              fontSize: 26,
              lineHeight: 1.25,
              color: danger ? palette.terminalRed : palette.terminalText,
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
                <span style={{color: danger ? palette.terminalRed : prefixColor}}>{prefix}</span>
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
