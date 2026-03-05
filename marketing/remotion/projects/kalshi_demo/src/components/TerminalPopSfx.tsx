import React from 'react';
import {Audio, Sequence, staticFile} from 'remotion';

type TerminalPopSfxProps = {
  frames: readonly number[];
  durationInFrames?: number;
  volume?: number;
  src?: string;
};

export const TerminalPopSfx: React.FC<TerminalPopSfxProps> = ({
  frames,
  durationInFrames = 20,
  volume = 0.35,
  src = 'bubble_popping_trim.m4a',
}) => {
  return (
    <>
      {frames.map((from, index) => (
        <Sequence key={`${from}-${index}`} from={from} durationInFrames={durationInFrames}>
          <Audio src={staticFile(src)} volume={volume} />
        </Sequence>
      ))}
    </>
  );
};
