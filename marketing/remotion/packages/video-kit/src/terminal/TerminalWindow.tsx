import React from 'react';
import {AbsoluteFill} from 'remotion';
import {DEFAULT_TERMINAL_THEME, type TerminalTheme} from './theme';

export type TerminalWindowProps = {
  x: number;
  y: number;
  width: number;
  height: number;
  zIndex?: number;
  rotation?: number;
  scale?: number;
  opacity?: number;
  focused?: boolean;
  contentStyle?: React.CSSProperties;
  theme?: Partial<TerminalTheme>;
  children: React.ReactNode;
};

export const TERMINAL_HEADER_HEIGHT = 34;

const dotStyle = (color: string): React.CSSProperties => ({
  width: 10,
  height: 10,
  borderRadius: 999,
  backgroundColor: color,
});

export const TerminalWindow: React.FC<TerminalWindowProps> = ({
  x,
  y,
  width,
  height,
  zIndex = 1,
  rotation = 0,
  scale = 1,
  opacity = 1,
  focused = false,
  contentStyle,
  theme,
  children,
}) => {
  const palette = {...DEFAULT_TERMINAL_THEME, ...theme};

  return (
    <AbsoluteFill
      style={{
        left: x,
        top: y,
        width,
        height,
        borderRadius: 12,
        overflow: 'hidden',
        border: focused ? palette.windowFocusedBorder : palette.windowBorder,
        boxShadow: focused ? palette.windowFocusedShadow : palette.windowShadow,
        transform: `rotate(${rotation}deg) scale(${scale})`,
        transformOrigin: 'center center',
        opacity,
        zIndex,
      }}
    >
      <div
        style={{
          height: TERMINAL_HEADER_HEIGHT,
          backgroundColor: palette.windowHeaderBg,
          borderBottom: palette.windowHeaderBorder,
          display: 'flex',
          alignItems: 'center',
          paddingLeft: 12,
          gap: 8,
        }}
      >
        <span style={dotStyle('#F87171')} />
        <span style={dotStyle('#FBBF24')} />
        <span style={dotStyle('#4ADE80')} />
      </div>
      <div
        style={{
          backgroundColor: palette.terminalBg,
          width: '100%',
          height: height - TERMINAL_HEADER_HEIGHT,
          padding: '12px 14px',
          position: 'relative',
          overflow: 'hidden',
          color: palette.terminalText,
          ...contentStyle,
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
