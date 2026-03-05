import React from 'react';
import {Composition} from 'remotion';
import {TerminalShowcase} from './compositions/TerminalShowcase';
import {LuxUiShowcase} from './compositions/LuxUiShowcase';
import {CodexSessionComparison} from './compositions/CodexSessionComparison';
import {CodexSessionReplica} from './compositions/CodexSessionReplica';
import {CODEX_SESSION_SOURCE_REPLICA} from '../../../packages/video-kit/src';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoKitTerminalShowcase"
        component={TerminalShowcase}
        durationInFrames={360}
        fps={60}
        width={1920}
        height={1080}
      />
      <Composition
        id="VideoKitLuxUiShowcase"
        component={LuxUiShowcase}
        durationInFrames={360}
        fps={60}
        width={1920}
        height={1080}
      />
      <Composition
        id="VideoKitCodexSessionReplica"
        component={CodexSessionReplica}
        durationInFrames={CODEX_SESSION_SOURCE_REPLICA.durationInFrames}
        fps={60}
        width={CODEX_SESSION_SOURCE_REPLICA.width}
        height={CODEX_SESSION_SOURCE_REPLICA.height}
      />
      <Composition
        id="VideoKitCodexSessionComparison"
        component={CodexSessionComparison}
        durationInFrames={CODEX_SESSION_SOURCE_REPLICA.durationInFrames}
        fps={60}
        width={1920}
        height={1080}
      />
    </>
  );
};
