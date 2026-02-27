import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {ChaosScene} from './ChaosScene';
import {interFontFamily} from '../config/fonts';
import {SCENE_FRAMES} from '../config/timing';

type OverlaySceneProps = {
  showDesktopBackground?: boolean;
  fullScreenPrimaryTerminal?: boolean;
};

const CLAMP = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

export const OverlayScene: React.FC<OverlaySceneProps> = ({
  showDesktopBackground = true,
  fullScreenPrimaryTerminal = false,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const textStartFrame = 0;
  const textEnter = spring({
    frame: Math.max(0, frame - textStartFrame),
    fps,
    config: {damping: 20, stiffness: 130, mass: 0.8},
  });
  const textOpacity = interpolate(textEnter, [0, 1], [0, 1], CLAMP);
  const textTranslateY = interpolate(textEnter, [0, 1], [24, 0], CLAMP);
  const textBlur = interpolate(textEnter, [0, 1], [8, 0], CLAMP);

  return (
    <AbsoluteFill style={{backgroundColor: '#000000'}}>
      <AbsoluteFill style={{zIndex: 0}}>
        <ChaosScene
          frameOverride={SCENE_FRAMES.chaos - 1}
          showDesktopBackground={showDesktopBackground}
          fullScreenPrimaryTerminal={fullScreenPrimaryTerminal}
          showCursor={false}
        />
      </AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: 650,
          display: 'flex',
          justifyContent: 'center',
          pointerEvents: 'none',
          zIndex: 1000,
        }}
      >
        <div
          style={{
            fontFamily: interFontFamily,
            fontSize: 68,
            fontWeight: 800,
            color: '#ffffff',
            textAlign: 'center',
            maxWidth: 1450,
            lineHeight: 1.1,
            textShadow: 'none',
            opacity: textOpacity,
            transform: `translateY(${textTranslateY}px)`,
            filter: `blur(${textBlur}px)`,
          }}
        >
          Do you know what your agents are doing?
        </div>
      </div>
    </AbsoluteFill>
  );
};
