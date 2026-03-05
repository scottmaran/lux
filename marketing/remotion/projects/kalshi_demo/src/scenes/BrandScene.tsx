import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {interFontFamily} from '../config/fonts';

import {loadFont as BrandFont} from '@remotion/google-fonts/Metal';

export const {fontFamily: BrandFontFamily} = BrandFont('normal', {
  weights: ['400'],
  subsets: ['latin'],
});

const CLAMP_OPTIONS = {
  extrapolateLeft: 'clamp' as const,
  extrapolateRight: 'clamp' as const,
};

type BrandSceneProps = {
  enableChime?: boolean;
};

export const BrandScene: React.FC<BrandSceneProps> = ({enableChime = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const logoStart = 10;
  const logoFadeFrames = Math.round(0.95 * fps);
  const taglineStart = logoStart + Math.round(0.75 * fps);
  const taglineFadeFrames = Math.round(1 * fps);
  const stripesFadeFrames = Math.round(0.8 * fps);

  const logoOpacity = interpolate(frame, [logoStart, logoStart + logoFadeFrames], [0, 1], CLAMP_OPTIONS);
  const taglineOpacity = interpolate(
    frame,
    [taglineStart, taglineStart + taglineFadeFrames],
    [0, 1],
    CLAMP_OPTIONS
  );
  const logoLift = interpolate(frame, [logoStart, logoStart + logoFadeFrames], [18, 0], {
    ...CLAMP_OPTIONS,
    easing: Easing.out(Easing.cubic),
  });
  const taglineLift = interpolate(frame, [taglineStart, taglineStart + taglineFadeFrames], [20, 0], {
    ...CLAMP_OPTIONS,
    easing: Easing.out(Easing.cubic),
  });
  const stripesOpacity = interpolate(frame, [logoStart, logoStart + stripesFadeFrames], [0, 1], {
    ...CLAMP_OPTIONS,
  });
  const chimeStart = logoStart + 6;
  const lightSweepOpacity = interpolate(frame, [logoStart - 6, logoStart + 18, logoStart + 98], [0, 0.55, 0], {
    ...CLAMP_OPTIONS,
    easing: Easing.inOut(Easing.cubic),
  });
  const lightSweepX = interpolate(frame, [logoStart - 6, logoStart + 98], [-65, 68], {
    ...CLAMP_OPTIONS,
    easing: Easing.inOut(Easing.cubic),
  });
  const haloOpacity = interpolate(frame, [logoStart, logoStart + 20, logoStart + 120], [0, 0.45, 0], {
    ...CLAMP_OPTIONS,
    easing: Easing.out(Easing.cubic),
  });
  const haloScale = interpolate(frame, [logoStart, logoStart + 116], [0.76, 1.26], {
    ...CLAMP_OPTIONS,
    easing: Easing.out(Easing.cubic),
  });

  return (
    <AbsoluteFill style={{backgroundColor: '#030712'}}>
      {enableChime ? (
        <Sequence from={chimeStart}>
          <Audio src={staticFile('chime_trimmed.m4a')} volume={0.24} />
        </Sequence>
      ) : null}
      <AbsoluteFill
        style={{
          backgroundImage:
            'radial-gradient(circle at 50% 18%, rgba(59, 130, 246, 0.24), rgba(13, 17, 23, 0) 48%)',
        }}
      />
      <AbsoluteFill
        style={{
          opacity: lightSweepOpacity,
          transform: `translateX(${lightSweepX}%)`,
          background:
            'linear-gradient(108deg, rgba(125, 211, 252, 0) 30%, rgba(125, 211, 252, 0.3) 50%, rgba(125, 211, 252, 0) 70%)',
          mixBlendMode: 'screen',
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '35%',
          width: 760,
          height: 760,
          borderRadius: '50%',
          transform: `translate(-50%, -50%) scale(${haloScale})`,
          opacity: haloOpacity,
          background:
            'radial-gradient(circle, rgba(147, 197, 253, 0.42) 0%, rgba(147, 197, 253, 0.14) 38%, rgba(147, 197, 253, 0) 72%)',
          filter: 'blur(2px)',
        }}
      />
      <AbsoluteFill
        style={{
          opacity: stripesOpacity,
          backgroundImage:
            'repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.04) 0px, rgba(255, 255, 255, 0.04) 22px, rgba(255, 255, 255, 0) 22px, rgba(255, 255, 255, 0) 58px)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          top: '33%',
          left: '50%',
          transform: `translate(-50%, ${logoLift}px)`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          opacity: logoOpacity,
        }}
      >
        <div style={{display: 'flex', alignItems: 'center', gap: 18}}>
          {/* <span
            style={{
              width: 34,
              height: 34,
              borderRadius: 999,
              border: '4px solid #2563EB',
              boxShadow: '0 0 0 6px rgba(37, 99, 235, 0.16), 0 0 26px rgba(59, 130, 246, 0.45)',
            }}
          /> */}
          <span
            style={{
              color: '#F8FAFC',
              fontSize: 130,
              fontWeight: 400,
              fontFamily: interFontFamily,
              letterSpacing: 0.5,
              lineHeight: 1,
            }}
          >
            Lux
          </span>
        </div>

        <div
          style={{
            marginTop: 8,
            color: '#6B7280',
            textAlign: 'center',
            fontSize: 60,
            fontWeight: 600,
            // letterSpacing: -0.4,
            // lineHeight: 1.08,
            // maxWidth: 1080,
          }}
        >
          The black box for your AI agents
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          top: '80%',
          left: '50%',
          transform: `translate(-50%, ${taglineLift}px)`,
          textAlign: 'center',
          color: '#F8FAFC',
          fontSize: 40,
          fontWeight: 700,
          fontFamily: interFontFamily,
          lineHeight: 1.04,
          letterSpacing: -1,
          opacity: taglineOpacity,
          whiteSpace: 'nowrap',
        }}
      >
        Every action. Logged. Whether they tell you or not.
      </div>
    </AbsoluteFill>
  );
};
