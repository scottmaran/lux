import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors} from '../config/colors';
import {interFontFamily} from '../config/fonts';
import {DashboardLayout} from '../../../../packages/video-kit/src';
import {DASHBOARD_RUNS, DASHBOARD_STATE_C} from '../config/terminalContent';

export const DifferentiatorScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const dashboardOpacity = interpolate(frame, [0, 60], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const darkBgOpacity = interpolate(frame, [30, 80], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const textIn = spring({
    frame: frame - 80,
    fps,
    config: {damping: 200},
    durationInFrames: 40,
  });

  const textOpacity = interpolate(textIn, [0, 1], [0, 1]);
  const textScale = interpolate(textIn, [0, 1], [0.95, 1]);

  const secondLineOpacity = interpolate(frame, [120, 150], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill>
      <DashboardLayout
        metrics={DASHBOARD_STATE_C.metrics}
        runs={DASHBOARD_RUNS}
        selectedRunId={DASHBOARD_STATE_C.selectedRunId}
        events={DASHBOARD_STATE_C.events}
        opacity={dashboardOpacity}
        scale={1}
      />

      <AbsoluteFill style={{backgroundColor: colors.darkBg, opacity: darkBgOpacity}} />

      <AbsoluteFill
        style={{
          justifyContent: 'center',
          alignItems: 'center',
          color: '#FFFFFF',
          fontFamily: interFontFamily,
        }}
      >
        <div
          style={{
            fontSize: 46,
            fontWeight: 600,
            opacity: textOpacity,
            transform: `scale(${textScale})`,
          }}
        >
          Zero integration.
        </div>
        <div
          style={{
            marginTop: 12,
            fontSize: 46,
            fontWeight: 600,
            opacity: textOpacity * secondLineOpacity,
          }}
        >
          Full visibility.
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
