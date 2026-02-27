import React from 'react';
import {TerminalPopSfx} from './TerminalPopSfx';

type MouseClickSfxProps = {
  frames: readonly number[];
  durationInFrames?: number;
  volume?: number;
};

export const MouseClickSfx: React.FC<MouseClickSfxProps> = ({
  frames,
  durationInFrames = 12,
  volume = 0.45,
}) => {
  return (
    <TerminalPopSfx
      frames={frames}
      durationInFrames={durationInFrames}
      volume={volume}
      src="mouse_click_trim.m4a"
    />
  );
};
