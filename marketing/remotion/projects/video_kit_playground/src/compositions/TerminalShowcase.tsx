import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  MouseCursor,
  ScrollingTerminal,
  TerminalWindow,
  TypingText,
  type TerminalLine,
} from '../../../../packages/video-kit/src';

const prompt = '> Build a safe autonomous trading monitor for Lux.';

const lines: TerminalLine[] = [
  {text: '[agent] Loading workspace and dependencies...', delay: 0},
  {text: '[agent] Initializing execution audit hooks...', delay: 30},
  {text: '[worker] Capturing process spawn graph...', delay: 58},
  {text: '[worker] Tracking file writes and deletions...', delay: 82},
  {text: '[ws] Streaming live network events...', delay: 106},
  {text: '[agent] Correlating events to active run IDs...', delay: 132},
  {text: '[agent] WARNING: unverified command detected', delay: 156, style: 'danger'},
  {text: '[agent] Requesting operator review checkpoint...', delay: 182, style: 'danger'},
  {text: '[agent] Audit trail complete. Ready for handoff.', delay: 218},
];

export const TerminalShowcase: React.FC = () => {
  const frame = useCurrentFrame();

  const cursorX = interpolate(frame, [0, 70, 130, 220, 320], [510, 1010, 1030, 760, 760], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const cursorY = interpolate(frame, [0, 70, 130, 220, 320], [330, 330, 710, 710, 710], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const clickStrength = Math.max(
    0,
    1 - Math.abs(frame - 78) / 8,
    1 - Math.abs(frame - 226) / 10,
  );

  const headingOpacity = interpolate(frame, [0, 18, 290, 330], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(circle at 15% 18%, rgba(34, 197, 94, 0.20), transparent 42%), linear-gradient(140deg, #020617 0%, #0f172a 52%, #111827 100%)',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 130,
          top: 72,
          color: '#E2E8F0',
          fontSize: 38,
          fontWeight: 700,
          letterSpacing: 0.6,
          opacity: headingOpacity,
        }}
      >
        Video Kit Terminal Showcase
      </div>

      <TerminalWindow x={220} y={210} width={1480} height={690} focused>
        <div style={{fontSize: 24, marginBottom: 16, color: '#E2E8F0'}}>
          <TypingText text={prompt} startFrame={12} charsPerFrame={2} />
        </div>
        <ScrollingTerminal lines={lines} startFrame={56} charsPerFrame={1.8} maxLines={12} />
      </TerminalWindow>

      <MouseCursor x={cursorX} y={cursorY} clickStrength={clickStrength} />
    </AbsoluteFill>
  );
};
