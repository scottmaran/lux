import React from 'react';
import {Composition} from 'remotion';
import {TerminalShowcase} from './compositions/TerminalShowcase';
import {LuxUiShowcase} from './compositions/LuxUiShowcase';

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
    </>
  );
};
