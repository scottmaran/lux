import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {SCENE_FRAMES} from './config/timing';
import {ChaosScene} from './scenes/ChaosScene';
import {OverlayScene} from './scenes/OverlayScene';
import {TransitionScene} from './scenes/TransitionScene';
import {DashboardScene} from './scenes/DashboardScene';
// import {DifferentiatorScene} from './scenes/DifferentiatorScene';
import {BrandScene} from './scenes/BrandScene';
import {ProblemIntroScene} from './scenes/ProblemIntroScene';
import {INSET_DASHBOARD_WINDOW} from './config/layout';
import {Callout} from './components/Callout';
import {TerminalPopSfx} from './components/TerminalPopSfx';

const SCENE_1_TYPING_SOUND_START = 40;
const SCENE_1_TYPING_SOUND_DURATION = 46; // frame 40 through 85 inclusive
const SCENE_1_TERMINAL_POP_FRAMES = [0, 145, 160, 170, 185, 200] as const;
const TERMINAL_POP_SOUND_DURATION = 20;

export const FullTerminalVideo: React.FC = () => {
  const {fps} = useVideoConfig();

  const introFrom = 0;
  const s1From = introFrom + SCENE_FRAMES.intro;
  const s2From = s1From + SCENE_FRAMES.chaos;
  const s3From = s2From + SCENE_FRAMES.overlay;
  const s4From = s3From + SCENE_FRAMES.sceneTransition;
  // const s5From = s4From + SCENE_FRAMES.dashboard;
  // const s6From = s5From + SCENE_FRAMES.differentiator;
  const s6From = s4From + SCENE_FRAMES.dashboard;

  return (
    <AbsoluteFill>
      <Sequence from={introFrom} durationInFrames={SCENE_FRAMES.intro}>
        <ProblemIntroScene />
      </Sequence>

      <Sequence from={s1From} durationInFrames={SCENE_FRAMES.chaos} premountFor={1 * fps}>
        <AbsoluteFill>
          <ChaosScene showDesktopBackground={false} enableClickSfx />
          <TerminalPopSfx
            frames={SCENE_1_TERMINAL_POP_FRAMES}
            durationInFrames={TERMINAL_POP_SOUND_DURATION}
          />
          <Sequence from={SCENE_1_TYPING_SOUND_START} durationInFrames={SCENE_1_TYPING_SOUND_DURATION}>
            <Audio src={staticFile('typing_sound_effect_trim.m4a')} volume={0.45} />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      <Sequence from={s2From} durationInFrames={SCENE_FRAMES.overlay} premountFor={1 * fps}>
        <OverlayScene showDesktopBackground={false} />
      </Sequence>

      <Sequence from={s3From} durationInFrames={SCENE_FRAMES.sceneTransition} premountFor={1 * fps}>
        <TransitionScene showDesktopBackground={false} insetDashboardFlow />
      </Sequence>

      <Sequence from={s4From} durationInFrames={SCENE_FRAMES.dashboard} premountFor={1 * fps}>
        <AbsoluteFill style={{backgroundColor: '#000000'}}>
          <ChaosScene
            frameOverride={SCENE_FRAMES.chaos - 1}
            showDesktopBackground={false}
            showCursor={false}
          />
          <AbsoluteFill style={{backgroundColor: 'rgba(0, 0, 0, 0.56)'}} />
          <DashboardScene insetWindow={INSET_DASHBOARD_WINDOW} />
          <Sequence from={20} durationInFrames={290}>
            <Callout
              kicker="Lux"
              title="OS-level agent monitoring"
              durationInFrames={400}
              position={{right: 750, bottom: 330}}
              // position={{right: 140, bottom: 230}}
            />
          </Sequence>
          <Sequence from={120} durationInFrames={190}>
            <Callout
              kicker=""
              title={'for when your Kalshi\n bots ignore their size limits'}
              durationInFrames={300}
              position={{left: 650, top: 760}}
            />
          </Sequence>
        </AbsoluteFill>
      </Sequence>

      {/* <Sequence from={s5From} durationInFrames={SCENE_FRAMES.differentiator} premountFor={1 * fps}>
        <DifferentiatorScene />
      </Sequence> */}

      <Sequence from={s6From} durationInFrames={SCENE_FRAMES.brand} premountFor={1 * fps}>
        <BrandScene />
      </Sequence>
    </AbsoluteFill>
  );
};
