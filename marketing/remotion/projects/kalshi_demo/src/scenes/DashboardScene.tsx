import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  useCurrentFrame,
} from 'remotion';
import {
  DASHBOARD_RUNS,
  DASHBOARD_STATE_A,
  DASHBOARD_STATE_B,
  DASHBOARD_STATE_C,
} from '../config/terminalContent';
import {DashboardLayout, MouseCursor, TERMINAL_HEADER_HEIGHT, TerminalWindow} from '../../../../packages/video-kit/src';
import {HEIGHT, WIDTH} from '../config/timing';
import {colors} from '../config/colors';
import {MouseClickSfx} from '../components/MouseClickSfx';

type DashboardSceneProps = {
  frameOverride?: number;
  insetWindow?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  showCursor?: boolean;
  enableClickSfx?: boolean;
};

type CursorPoint = {
  frame: number;
  x: number;
  y: number;
};

const switchAToB = 70;
const switchBToC = 256;
const switchDuration = 26;
const clickFrames = [switchAToB, switchBToC] as const;

const path: CursorPoint[] = [
  {frame: 0, x: 1516, y: 475},
  {frame: 30, x: 1516, y: 475},
  {frame: switchAToB, x: 1516, y: 700},
  {frame: (switchAToB+switchBToC)/2, x: 1000, y: 600},
  {frame: switchBToC, x: 1516, y: 812},
  {frame: switchBToC+50, x: 1000, y: 800},
  {frame: switchBToC+110, x: 1150, y: 800},
];

const getCursorPosition = (frame: number): {x: number; y: number} => {
  if (frame <= path[0].frame) {
    return {x: path[0].x, y: path[0].y};
  }

  for (let i = 0; i < path.length - 1; i += 1) {
    const a = path[i];
    const b = path[i + 1];
    if (frame <= b.frame) {
      return {
        x: interpolate(frame, [a.frame, b.frame], [a.x, b.x], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.cubic),
        }),
        y: interpolate(frame, [a.frame, b.frame], [a.y, b.y], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
          easing: Easing.inOut(Easing.cubic),
        }),
      };
    }
  }

  const tail = path[path.length - 1];
  return {x: tail.x, y: tail.y};
};

const getClickStrength = (frame: number): number => {
  const deltas = [Math.abs(frame - switchAToB), Math.abs(frame - switchBToC)];
  const min = Math.min(...deltas);
  if (min > 8) {
    return 0;
  }

  return 1 - min / 8;
};

export const DashboardScene: React.FC<DashboardSceneProps> = ({
  frameOverride,
  insetWindow,
  showCursor = true,
  enableClickSfx = true,
}) => {
  const sceneFrame = useCurrentFrame();
  const frame = frameOverride ?? sceneFrame;

  let selectedRunId = DASHBOARD_STATE_A.selectedRunId;
  let metrics = DASHBOARD_STATE_A.metrics;
  let events = DASHBOARD_STATE_A.events;
  let incomingEvents = undefined;
  let timelineBlend = 0;
  let pulseRunId = undefined;

  if (frame >= switchAToB && frame < switchAToB + switchDuration) {
    selectedRunId = DASHBOARD_STATE_B.selectedRunId;
    metrics = DASHBOARD_STATE_B.metrics;
    events = DASHBOARD_STATE_A.events;
    incomingEvents = DASHBOARD_STATE_B.events;
    timelineBlend = interpolate(frame, [switchAToB, switchAToB + switchDuration], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    pulseRunId = DASHBOARD_STATE_B.selectedRunId;
  } else if (frame >= switchAToB + switchDuration && frame < switchBToC) {
    selectedRunId = DASHBOARD_STATE_B.selectedRunId;
    metrics = DASHBOARD_STATE_B.metrics;
    events = DASHBOARD_STATE_B.events;
  } else if (frame >= switchBToC && frame < switchBToC + switchDuration) {
    selectedRunId = DASHBOARD_STATE_C.selectedRunId;
    metrics = DASHBOARD_STATE_C.metrics;
    events = DASHBOARD_STATE_B.events;
    incomingEvents = DASHBOARD_STATE_C.events;
    timelineBlend = interpolate(frame, [switchBToC, switchBToC + switchDuration], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    pulseRunId = DASHBOARD_STATE_C.selectedRunId;
  } else if (frame >= switchBToC + switchDuration) {
    selectedRunId = DASHBOARD_STATE_C.selectedRunId;
    metrics = DASHBOARD_STATE_C.metrics;
    events = DASHBOARD_STATE_C.events;
  }

  const cursor = getCursorPosition(frame);

  const dashboardContent = (
    <>
      <DashboardLayout
        metrics={metrics}
        runs={DASHBOARD_RUNS}
        selectedRunId={selectedRunId}
        events={events}
        incomingEvents={incomingEvents}
        timelineBlend={timelineBlend}
        pulseRunId={pulseRunId}
      />
      {showCursor && enableClickSfx ? <MouseClickSfx frames={clickFrames} /> : null}
      {showCursor ? <MouseCursor x={cursor.x} y={cursor.y} clickStrength={getClickStrength(frame)} /> : null}
    </>
  );

  if (insetWindow) {
    const insetHeight = insetWindow.height - TERMINAL_HEADER_HEIGHT;
    const scaleX = insetWindow.width / WIDTH;
    const scaleY = insetHeight / HEIGHT;

    return (
      <AbsoluteFill>
        <TerminalWindow
          x={insetWindow.x}
          y={insetWindow.y}
          width={insetWindow.width}
          height={insetWindow.height}
          zIndex={45}
          focused
          contentStyle={{
            backgroundColor: colors.dashboardBg,
            padding: 0,
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: 0,
              width: WIDTH,
              height: HEIGHT,
              transform: `scale(${scaleX}, ${scaleY})`,
              transformOrigin: 'top left',
            }}
          >
            {dashboardContent}
          </div>
        </TerminalWindow>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      {dashboardContent}
    </AbsoluteFill>
  );
};
