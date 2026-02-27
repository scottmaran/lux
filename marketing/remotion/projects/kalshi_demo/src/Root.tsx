import React from 'react';
import {Composition} from 'remotion';
import {HEIGHT, FPS, TOTAL_FRAMES, WIDTH} from './config/timing';
import {FullTerminalVideo} from './FullTerminalVideo';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="LassoFullTerminal"
        component={FullTerminalVideo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    </>
  );
};
