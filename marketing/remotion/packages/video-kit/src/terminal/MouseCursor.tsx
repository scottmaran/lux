import React from 'react';
import {AbsoluteFill} from 'remotion';

export type MouseCursorProps = {
  x: number;
  y: number;
  zIndex?: number;
  clickStrength?: number;
  scale?: number;
  opacity?: number;
};

export const MouseCursor: React.FC<MouseCursorProps> = ({
  x,
  y,
  zIndex = 999,
  clickStrength = 0,
  scale = 1,
  opacity = 1,
}) => {
  const ringScale = 1 + clickStrength * 1.4;
  const ringOpacity = 0.35 * clickStrength;

  return (
    <AbsoluteFill
      style={{
        left: x,
        top: y,
        width: 36,
        height: 42,
        pointerEvents: 'none',
        zIndex,
        transform: `scale(${scale})`,
        opacity,
      }}
    >
      <div
        style={{
          width: 0,
          height: 0,
          borderLeft: '8px solid transparent',
          borderRight: '8px solid transparent',
          borderBottom: '22px solid #FFFFFF',
          transform: 'rotate(-35deg)',
          transformOrigin: 'center bottom',
          filter: 'drop-shadow(0 0 1px rgba(0,0,0,0.9)) drop-shadow(0 2px 5px rgba(0,0,0,0.45))',
          marginLeft: 6,
          marginTop: 2,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: 6,
          top: 2,
          width: 20,
          height: 20,
          borderRadius: 999,
          border: '2px solid rgba(255,255,255,0.65)',
          transform: `scale(${ringScale})`,
          opacity: ringOpacity,
        }}
      />
    </AbsoluteFill>
  );
};
