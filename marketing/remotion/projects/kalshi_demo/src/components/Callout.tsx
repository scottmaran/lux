import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {interFontFamily} from '../config/fonts';

type CalloutProps = {
  kicker: string;
  title: string;
  lines?: string[];
  durationInFrames: number;
  align?: 'left' | 'right';
  position?: Pick<React.CSSProperties, 'top' | 'right' | 'bottom' | 'left'>;
};

const fadeInOut = (frame: number, durationInFrames: number): number => {
  const fadeInFrames = Math.min(24, Math.max(1, Math.round(durationInFrames * 0.15)));
  const fadeOutFrames = fadeInFrames;
  const holdEnd = Math.max(fadeInFrames, durationInFrames - fadeOutFrames);

  return interpolate(frame, [0, fadeInFrames, holdEnd, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
};

export const Callout: React.FC<CalloutProps> = ({
  kicker,
  title,
  lines = [],
  durationInFrames,
  align = 'left',
  position,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({
    frame,
    fps,
    config: {damping: 200, mass: 0.65},
  });
  const translateY = interpolate(enter, [0, 1], [26, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = fadeInOut(frame, durationInFrames);
  const hasHorizontalPosition = position?.left !== undefined || position?.right !== undefined;
  const hasVerticalPosition = position?.top !== undefined || position?.bottom !== undefined;
  const resolvedPosition = {
    ...(!hasVerticalPosition ? {bottom: 240} : {}),
    ...(!hasHorizontalPosition ? (align === 'right' ? {right: 240} : {left: 240}) : {}),
    ...position,
  } satisfies Pick<React.CSSProperties, 'top' | 'right' | 'bottom' | 'left'>;

  return (
    <AbsoluteFill
      style={{
        fontFamily: interFontFamily,
        pointerEvents: 'none',
        zIndex: 1600,
      }}
    >
      <div
        style={{
          position: 'absolute',
          width: 520,
          padding: '22px 26px',
          borderRadius: 22,
          background: 'rgba(16, 23, 37, 0.9)',
          border: '1px solid rgba(59, 130, 246, 0.35)',
          boxShadow: '0 28px 60px rgba(0, 0, 0, 0.45)',
          transform: `translateY(${translateY}px)`,
          opacity,
          ...resolvedPosition,
        }}
      >
        <div
          style={{
            textTransform: 'uppercase',
            letterSpacing: 2.2,
            fontSize: 12,
            fontWeight: 600,
            color: '#60A5FA',
          }}
        >
          {kicker}
        </div>
        <div
          style={{
            fontSize: 30,
            fontWeight: 600,
            marginTop: 10,
            color: '#F8FAFC',
            lineHeight: 1.15,
            whiteSpace: 'pre-line',
          }}
        >
          {title}
        </div>
        {lines.length > 0 ? (
          <div style={{marginTop: 14, display: 'grid', gap: 8}}>
            {lines.map((line) => (
              <div
                key={line}
                style={{
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start',
                  fontSize: 18,
                  color: '#CBD5E1',
                }}
              >
                <span
                  style={{
                    color: '#2563EB',
                    fontWeight: 700,
                    lineHeight: 1.3,
                  }}
                >
                  -
                </span>
                <span style={{lineHeight: 1.35}}>{line}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
