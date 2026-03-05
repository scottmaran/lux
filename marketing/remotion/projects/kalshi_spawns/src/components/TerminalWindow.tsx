import React from 'react';
import {AbsoluteFill} from 'remotion';
import {colors} from '../config/colors';

type TerminalWindowProps = {
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
  children,
}) => {
  return (
    <AbsoluteFill
      style={{
        left: x,
        top: y,
        width,
        height,
        borderRadius: 12,
        overflow: 'hidden',
        border: focused ? '1px solid rgba(125, 211, 252, 0.5)' : '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: focused
          ? '0 0 0 1px rgba(125, 211, 252, 0.35), 0 16px 40px rgba(0, 0, 0, 0.5)'
          : '0 14px 34px rgba(0, 0, 0, 0.45)',
        transform: `rotate(${rotation}deg) scale(${scale})`,
        transformOrigin: 'center center',
        opacity,
        zIndex,
      }}
    >
      <div
        style={{
          height: TERMINAL_HEADER_HEIGHT,
          backgroundColor: '#27293D',
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
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
          backgroundColor: colors.terminalBg,
          width: '100%',
          height: height - TERMINAL_HEADER_HEIGHT,
          padding: '12px 14px',
          position: 'relative',
          overflow: 'hidden',
          color: colors.terminalText,
          ...contentStyle,
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};
