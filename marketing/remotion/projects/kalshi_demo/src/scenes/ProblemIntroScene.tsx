import React from 'react';
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';
import {interFontFamily} from '../config/fonts';
import {SCENE_FRAMES} from '../config/timing';

const CLAMP = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

export const ProblemIntroScene: React.FC = () => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 22, 86, SCENE_FRAMES.intro], [0, 1, 1, 0], {
    ...CLAMP,
    easing: Easing.inOut(Easing.cubic),
  });

  const translateY = interpolate(frame, [0, 24, SCENE_FRAMES.intro], [26, 0, -14], {
    ...CLAMP,
    easing: Easing.inOut(Easing.cubic),
  });

  const blur = interpolate(frame, [0, 18, 96, SCENE_FRAMES.intro], [8, 0, 0, 6], CLAMP);

  return (
    <AbsoluteFill style={{backgroundColor: '#020617'}}>
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 50% 22%, rgba(20, 57, 117, 0.26), rgba(2, 6, 23, 0) 56%)',
        }}
      />
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 160px',
        }}
      >
        <div
          style={{
            color: '#E2E8F0',
            fontFamily: interFontFamily,
            fontSize: 74,
            fontWeight: 700,
            lineHeight: 1.08,
            letterSpacing: -1,
            textAlign: 'center',
            textWrap: 'balance',
            opacity,
            transform: `translateY(${translateY}px)`,
            filter: `blur(${blur}px)`,
          }}
        >
          As agents get better, <br></br>
          we're giving them more access
        </div>
      </div>
    </AbsoluteFill>
  );
};
