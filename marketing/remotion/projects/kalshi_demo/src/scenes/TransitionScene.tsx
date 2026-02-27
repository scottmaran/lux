import React from 'react';
import {AbsoluteFill, Audio, interpolate, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {colors} from '../config/colors';
import {ChaosScene} from './ChaosScene';
import {DashboardScene} from './DashboardScene';
import {DashboardLayout, TerminalWindow, TypingText} from '../../../../packages/video-kit/src';
import {DASHBOARD_RUNS, DASHBOARD_STATE_A} from '../config/terminalContent';
import {SCENE_FRAMES} from '../config/timing';
import {COMMAND_TERMINAL_WINDOW, INSET_DASHBOARD_WINDOW} from '../config/layout';
import {jetBrainsMonoFamily} from '../config/fonts';
import {TerminalPopSfx} from '../components/TerminalPopSfx';

type TransitionSceneProps = {
  showDesktopBackground?: boolean;
  fullScreenPrimaryTerminal?: boolean;
  insetDashboardFlow?: boolean;
};

export const TransitionScene: React.FC<TransitionSceneProps> = ({
  showDesktopBackground = true,
  fullScreenPrimaryTerminal = false,
  insetDashboardFlow = false,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  if (!insetDashboardFlow) {
    const cutToDashboardFrame = 60;

    return (
      <AbsoluteFill style={{backgroundColor: '#000000'}}>
        {frame < cutToDashboardFrame ? (
          <ChaosScene
            frameOverride={SCENE_FRAMES.chaos - 1}
            showDesktopBackground={showDesktopBackground}
            fullScreenPrimaryTerminal={fullScreenPrimaryTerminal}
            showCursor={false}
          />
        ) : (
          <DashboardLayout
            metrics={DASHBOARD_STATE_A.metrics}
            runs={DASHBOARD_RUNS}
            selectedRunId={DASHBOARD_STATE_A.selectedRunId}
            events={DASHBOARD_STATE_A.events}
          />
        )}
      </AbsoluteFill>
    );
  }

  const commandText = 'lux logs';
  const commandWindowAppearFrame = 0;
  const commandStart = 30;
  const commandTypingSoundStart = 32;
  const commandTypingSoundEnd = 60;
  const commandTypingSoundDuration = commandTypingSoundEnd - commandTypingSoundStart + 1;
  const charsPerFrame = 0.35;
  const commandDoneFrame = commandStart + Math.ceil(commandText.length / charsPerFrame);
  const enterFrame = commandDoneFrame + 12;
  const appLaunchFrame = enterFrame + 40;
  const appWindowPopFrame = appLaunchFrame;

  const commandWindowEntry = spring({
    frame: Math.max(0, frame - commandWindowAppearFrame),
    fps,
    config: {damping: 16, stiffness: 92},
    durationInFrames: 42,
  });

  const commandWindowScale = interpolate(commandWindowEntry, [0, 1], [0.9, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const commandWindowTranslateY = interpolate(commandWindowEntry, [0, 1], [22, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const appWindowEntry = spring({
    frame: Math.max(0, frame - appLaunchFrame),
    fps,
    config: {damping: 18, stiffness: 95},
    durationInFrames: 88,
  });

  const appScale = interpolate(appWindowEntry, [0, 0.75, 1], [0.84, 1.03, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const appTranslateY = interpolate(appWindowEntry, [0, 1], [32, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{backgroundColor: '#000000'}}>
      <TerminalPopSfx frames={[commandWindowAppearFrame, appWindowPopFrame]} />

      <Sequence from={commandTypingSoundStart} durationInFrames={commandTypingSoundDuration}>
        <Audio src={staticFile('typing_sound_effect_trim.m4a')} volume={0.45} />
      </Sequence>

      <ChaosScene
        frameOverride={SCENE_FRAMES.chaos - 1}
        showDesktopBackground={showDesktopBackground}
        fullScreenPrimaryTerminal={fullScreenPrimaryTerminal}
        showCursor={false}
      />

      {frame >= commandWindowAppearFrame ? (
        <AbsoluteFill
          style={{
            transform: `translateY(${commandWindowTranslateY}px)`,
            transformOrigin: '50% 50%',
            zIndex: 1000,
          }}
        >
          <TerminalWindow
            x={COMMAND_TERMINAL_WINDOW.x}
            y={COMMAND_TERMINAL_WINDOW.y}
            width={COMMAND_TERMINAL_WINDOW.width}
            height={COMMAND_TERMINAL_WINDOW.height}
            zIndex={1000}
            focused={frame < appLaunchFrame + 14}
            scale={commandWindowScale}
          >
            <div
              style={{
                fontFamily: jetBrainsMonoFamily,
                fontSize: 42,
                lineHeight: 1.35,
              }}
            >
              <span style={{color: colors.terminalText}}>&gt; </span>
              <TypingText
                text={commandText}
                startFrame={commandStart}
                charsPerFrame={charsPerFrame}
                frame={frame}
                cursorChar="█"
                blinkRate={24}
              />
            </div>

            {frame >= enterFrame ? (
              <div
                style={{
                  marginTop: 18,
                  fontFamily: jetBrainsMonoFamily,
                  fontSize: 25,
                  lineHeight: 1.35,
                  color: colors.terminalGreen,
                }}
              >
                [lux] Opening verified activity dashboard...
              </div>
            ) : null}

            {frame >= enterFrame + 13 ? (
              <div
                style={{
                  marginTop: 10,
                  fontFamily: jetBrainsMonoFamily,
                  fontSize: 22,
                  lineHeight: 1.35,
                  color: colors.terminalText,
                }}
              >
                [lux] Loading run context: session_main_2026
              </div>
            ) : null}
          </TerminalWindow>
        </AbsoluteFill>
      ) : null}

      {frame >= appLaunchFrame ? (
        <AbsoluteFill
          style={{
            transform: `translateY(${appTranslateY}px) scale(${appScale})`,
            transformOrigin: '50% 54%',
            zIndex: 2000,
          }}
        >
          <DashboardScene frameOverride={0} insetWindow={INSET_DASHBOARD_WINDOW} showCursor={false} />
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
