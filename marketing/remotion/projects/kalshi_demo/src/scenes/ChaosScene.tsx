import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {colors} from '../config/colors';
import {jetBrainsMonoFamily} from '../config/fonts';
import {
  TERMINAL_1_LINES,
  TERMINAL_2_LINES,
  TERMINAL_3_DISCOVERY_LINES,
  TERMINAL_3_LINES,
  TERMINAL_4_LINES,
  TERMINAL_5_DISCOVERY_LINES,
  TERMINAL_5_LINES,
  TERMINAL_6_DISCOVERY_LINES,
  TERMINAL_NOISE_LINES,
} from '../config/terminalContent';
import type {TerminalLine} from '../config/terminalContent';
import {MouseCursor, ScrollingTerminal, TerminalWindow, TypingText} from '../../../../packages/video-kit/src';
import {MouseClickSfx} from '../components/MouseClickSfx';

type ChaosSceneProps = {
  frameOverride?: number;
  showDesktopBackground?: boolean;
  fullScreenPrimaryTerminal?: boolean;
  showCursor?: boolean;
  enableClickSfx?: boolean;
};

type CursorPoint = {
  frame: number;
  x: number;
  y: number;
};

const promptText = 'Write me a trading bot for Kalshi. Make no mistakes.';
const PROMPT_TYPING_START = 40;
const PROMPT_TYPING_DURATION = 45;
const PROMPT_CHARS_PER_FRAME = promptText.length / PROMPT_TYPING_DURATION;
const PROMPT_DONE_FRAME = PROMPT_TYPING_START + PROMPT_TYPING_DURATION;
const ENTER_PRESS_FRAME = PROMPT_DONE_FRAME + 12;
const ACTIVITY_START_FRAME = ENTER_PRESS_FRAME + 4;
const discoveryStart = 260;
const pauseStart = 380;
const TERMINAL_3_FOCUS_FRAME = 425;
const TERMINAL_3_CLICK_FRAME = 415;
const SCREEN_RECT = {
  x: 278,
  y: 116,
  width: 1364,
  height: 688,
  borderRadius: 4,
} as const;
const SPAWN_FRAMES = {
  t2: 145,
  t3: 200,
  t4: 160,
  t5: 170,
  t6: 185,
} as const;

const withOffset = (lines: TerminalLine[], offset: number): TerminalLine[] => {
  return lines.map((line) => ({
    ...line,
    delay: line.delay + offset,
  }));
};

const repeatLines = (lines: TerminalLine[], repeats: number, chunkOffset: number): TerminalLine[] => {
  const output: TerminalLine[] = [];
  for (let i = 0; i < repeats; i += 1) {
    output.push(...withOffset(lines, i * chunkOffset));
  }

  return output;
};

const cursorPath: CursorPoint[] = [
  {frame: 135, x: 550, y: 350},
  {frame: 192, x: 1500, y: 280},
  {frame: 212, x: 1500, y: 780},
  {frame: 234, x: 500, y: 880},
  {frame: 340, x: 465, y: 335},
  {frame: TERMINAL_3_CLICK_FRAME-20, x: 370, y: 390},
  {frame: TERMINAL_3_CLICK_FRAME, x: 370, y: 390},
  {frame: TERMINAL_3_CLICK_FRAME+20, x: 370, y: 390},
  {frame: 468, x: 750, y: 680},
];

const clickFrames = [TERMINAL_3_CLICK_FRAME];

const getCursorPosition = (frame: number): {x: number; y: number} => {
  if (frame <= cursorPath[0].frame) {
    return {x: cursorPath[0].x, y: cursorPath[0].y};
  }

  for (let i = 0; i < cursorPath.length - 1; i += 1) {
    const a = cursorPath[i];
    const b = cursorPath[i + 1];
    if (frame <= b.frame) {
      const x = interpolate(frame, [a.frame, b.frame], [a.x, b.x], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      });
      const y = interpolate(frame, [a.frame, b.frame], [a.y, b.y], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
        easing: Easing.inOut(Easing.cubic),
      });
      return {x, y};
    }
  }

  const last = cursorPath[cursorPath.length - 1];
  return {x: last.x, y: last.y};
};

const getClickStrength = (frame: number): number => {
  return clickFrames.reduce((best, clickFrame) => {
    const delta = Math.abs(frame - clickFrame);
    const value = delta > 8 ? 0 : 1 - delta / 8;
    return Math.max(best, value);
  }, 0);
};

const getFocusId = (frame: number): string => {
  return frame >= TERMINAL_3_FOCUS_FRAME ? 't3' : 't1';
};

const getTerminalEntry = (frame: number, spawnFrame: number, fps: number): number => {
  if (frame < spawnFrame) {
    return 0;
  }

  return spring({
    frame: frame - spawnFrame,
    fps,
    config: {damping: 16, stiffness: 70, mass: 1.2},
  });
};

export const ChaosScene: React.FC<ChaosSceneProps> = ({
  frameOverride,
  showDesktopBackground = true,
  fullScreenPrimaryTerminal = false,
  showCursor = true,
  enableClickSfx = false,
}) => {
  const sceneFrame = useCurrentFrame();
  const frame = frameOverride ?? sceneFrame;
  const contentFrame = frame >= pauseStart ? pauseStart - 1 : frame;
  const {fps} = useVideoConfig();

  const focusId = getFocusId(frame);
  const {x: cursorX, y: cursorY} = getCursorPosition(frame);
  const clickStrength = getClickStrength(frame);

  const backgroundSpeed =
    contentFrame >= discoveryStart
      ? interpolate(contentFrame, [discoveryStart, 470], [1, 0.1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
      : 1;

  const terminal3Speed =
    contentFrame >= discoveryStart
      ? interpolate(contentFrame, [discoveryStart, 500], [0.7, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
      : 1;

  const terminal5Speed =
    contentFrame >= discoveryStart
      ? interpolate(contentFrame, [discoveryStart, 510], [0.8, 0.45], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
      : 1;

  const terminal6Speed =
    contentFrame >= 500 ? 0.75 : contentFrame >= discoveryStart ? 1.5 : 2.2;

  const discoveryDim = frame >= TERMINAL_3_FOCUS_FRAME;

  const terminal3Lines = [
    ...TERMINAL_3_LINES,
    ...withOffset(TERMINAL_3_DISCOVERY_LINES, discoveryStart - SPAWN_FRAMES.t3),
  ];

  const terminal5Lines = [
    ...TERMINAL_5_LINES,
    ...withOffset(TERMINAL_5_DISCOVERY_LINES, 500 - SPAWN_FRAMES.t5),
  ];

  const terminal6Lines = [
    ...repeatLines(TERMINAL_NOISE_LINES, 4, 58),
    ...withOffset(TERMINAL_6_DISCOVERY_LINES, 510 - SPAWN_FRAMES.t6),
  ];

  const terminalOpacity = (id: string, entry: number): number => {
    const dim = discoveryDim && id !== 't3' ? 0.45 : 1;
    return entry * dim;
  };
  const terminal1Frame =
    frame <= ACTIVITY_START_FRAME
      ? frame
      : ACTIVITY_START_FRAME + Math.floor((frame - ACTIVITY_START_FRAME) * 1.25);
  const terminal1Speed = 1;

  const viewportOffsetX = showDesktopBackground ? SCREEN_RECT.x : 0;
  const viewportOffsetY = showDesktopBackground ? SCREEN_RECT.y : 0;
  const toViewportX = (x: number): number => x - viewportOffsetX;
  const toViewportY = (y: number): number => y - viewportOffsetY;
  const useFullScreenPrimary = fullScreenPrimaryTerminal && !showDesktopBackground;
  const primaryTerminalX = useFullScreenPrimary ? 0 : toViewportX(510);
  const primaryTerminalY = useFullScreenPrimary ? 0 : toViewportY(270);
  const primaryTerminalWidth = useFullScreenPrimary ? 1920 : 900;
  const primaryTerminalHeight = useFullScreenPrimary ? 1080 : 500;
  // const primaryTerminalX = useFullScreenPrimary ? 0 : toViewportX(150);
  // const primaryTerminalY = useFullScreenPrimary ? 0 : toViewportY(150);
  // const primaryTerminalWidth = useFullScreenPrimary ? 1920 : 1200;
  // const primaryTerminalHeight = useFullScreenPrimary ? 1080 : 750;

  const primaryTerminalScale = useFullScreenPrimary ? 1 : 0.97 + getTerminalEntry(frame, 0, fps) * 0.03;
  const viewportStyle: React.CSSProperties = showDesktopBackground
    ? {
        left: SCREEN_RECT.x,
        top: SCREEN_RECT.y,
        width: SCREEN_RECT.width,
        height: SCREEN_RECT.height,
        borderRadius: SCREEN_RECT.borderRadius,
        overflow: 'hidden',
      }
    : {
        left: 0,
        top: 0,
        width: '100%',
        height: '100%',
        overflow: 'visible',
      };

  return (
    <AbsoluteFill
      style={{
        fontFamily: jetBrainsMonoFamily,
      }}
    >
      {enableClickSfx ? <MouseClickSfx frames={clickFrames} /> : null}

      {!showDesktopBackground ? (
        <AbsoluteFill
          style={{
            backgroundColor: '#000000',
          }}
        />
      ) : null}
      {showDesktopBackground ? (
        <Img
          src={staticFile('macos-desktop.svg')}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
          }}
        />
      ) : null}
      {showDesktopBackground ? (
        <AbsoluteFill
          style={{
            background: 'radial-gradient(circle at 40% 22%, rgba(8, 12, 24, 0.08) 0%, rgba(2, 6, 23, 0.4) 72%)',
          }}
        />
      ) : null}
      <AbsoluteFill style={viewportStyle}>
        {(() => {
          const entry = getTerminalEntry(frame, 0, fps);
          return (
            <TerminalWindow
              x={primaryTerminalX}
              y={primaryTerminalY}
              width={primaryTerminalWidth}
              height={primaryTerminalHeight}
              zIndex={focusId === 't1' ? 30 : 8}
              rotation={0}
              scale={primaryTerminalScale}
              opacity={terminalOpacity('t1', entry)}
              focused={focusId === 't1' && !discoveryDim}
            >
              <div style={{fontSize: 46, lineHeight: 1.4}}>
                <span style={{color: colors.terminalText}}>&gt; </span>
                <TypingText
                  text={promptText}
                  startFrame={PROMPT_TYPING_START}
                  charsPerFrame={PROMPT_CHARS_PER_FRAME}
                  frame={contentFrame}
                  cursorChar="█"
                  blinkRate={30}
                />
              </div>
              <div style={{marginTop: 16}}>
                <ScrollingTerminal
                  lines={TERMINAL_1_LINES}
                  startFrame={ACTIVITY_START_FRAME}
                  frame={terminal1Frame}
                  charsPerFrame={1.35}
                  speedMultiplier={terminal1Speed}
                  maxLines={10}
                />
              </div>
            </TerminalWindow>
          );
        })()}

        {(() => {
          const entry = getTerminalEntry(frame, SPAWN_FRAMES.t2, fps);
          if (entry <= 0) {
            return null;
          }
          return (
            <TerminalWindow
              x={toViewportX(1020)}
              y={toViewportY(110)}
              width={720}
              height={380}
              zIndex={focusId === 't2' ? 33 : 4}
              rotation={0}
              scale={0.86 + entry * 0.14}
              opacity={terminalOpacity('t2', entry)}
              focused={focusId === 't2' && !discoveryDim}
            >
              <ScrollingTerminal
                lines={TERMINAL_2_LINES}
                startFrame={SPAWN_FRAMES.t2}
                frame={contentFrame}
                charsPerFrame={1.7}
                speedMultiplier={backgroundSpeed}
                maxLines={10}
              />
            </TerminalWindow>
          );
        })()}

        {(() => {
          const entry = getTerminalEntry(frame, SPAWN_FRAMES.t3, fps);
          if (entry <= 0) {
            return null;
          }
          return (
            <TerminalWindow
              x={toViewportX(24)}
              y={toViewportY(170)}
              width={760}
              height={400}
              zIndex={focusId === 't3' ? 40 : 35}
              rotation={0}
              scale={0.86 + entry * 0.14}
              opacity={terminalOpacity('t3', entry)}
              focused={focusId === 't3'}
            >
              <ScrollingTerminal
                lines={terminal3Lines}
                startFrame={SPAWN_FRAMES.t3}
                frame={contentFrame}
                charsPerFrame={1.7}
                speedMultiplier={terminal3Speed}
                maxLines={11}
              />
              {frame >= 535 ? (
                <div
                  style={{
                    marginTop: 6,
                    fontSize: 16,
                    color: colors.terminalCursor,
                    opacity: Math.floor(frame / 30) % 2 === 0 ? 1 : 0,
                  }}
                >
                  █
                </div>
              ) : null}
            </TerminalWindow>
          );
        })()}

        {(() => {
          const entry = getTerminalEntry(frame, SPAWN_FRAMES.t4, fps);
          if (entry <= 0) {
            return null;
          }
          return (
            <TerminalWindow
              x={toViewportX(1030)}
              y={toViewportY(590)}
              width={700}
              height={350}
              zIndex={4}
              rotation={0}
              scale={0.86 + entry * 0.14}
              opacity={terminalOpacity('t4', entry)}
              focused={focusId === 't4' && !discoveryDim}
            >
              <ScrollingTerminal
                lines={TERMINAL_4_LINES}
                startFrame={SPAWN_FRAMES.t4}
                frame={contentFrame}
                charsPerFrame={1.8}
                speedMultiplier={backgroundSpeed}
                maxLines={9}
              />
            </TerminalWindow>
          );
        })()}

        {(() => {
          const entry = getTerminalEntry(frame, SPAWN_FRAMES.t5, fps);
          if (entry <= 0) {
            return null;
          }
          return (
            <TerminalWindow
              x={toViewportX(250)}
              y={toViewportY(710)}
              width={560}
              height={280}
              zIndex={4}
              rotation={0}
              scale={0.86 + entry * 0.14}
              opacity={terminalOpacity('t5', entry)}
              focused={focusId === 't5' && !discoveryDim}
            >
              <ScrollingTerminal
                lines={terminal5Lines}
                startFrame={SPAWN_FRAMES.t5}
                frame={contentFrame}
                charsPerFrame={1.8}
                speedMultiplier={terminal5Speed}
                maxLines={10}
              />
            </TerminalWindow>
          );
        })()}

        {(() => {
          const entry = getTerminalEntry(frame, SPAWN_FRAMES.t6, fps);
          if (entry <= 0) {
            return null;
          }
          return (
            <TerminalWindow
              x={1028}
              y={24}
              width={620}
              height={320}
              zIndex={4}
              rotation={0}
              scale={0.86 + entry * 0.14}
              opacity={terminalOpacity('t6', entry)}
              focused={false}
            >
              <ScrollingTerminal
                lines={terminal6Lines}
                startFrame={SPAWN_FRAMES.t6}
                frame={contentFrame}
                charsPerFrame={3.4}
                speedMultiplier={terminal6Speed}
                maxLines={9}
              />
            </TerminalWindow>
          );
        })()}

        {showCursor ? (
          <MouseCursor
            x={toViewportX(cursorX)}
            y={toViewportY(cursorY)}
            clickStrength={clickStrength}
          />
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
