import React from 'react';
import {Composition} from 'remotion';
import {Main} from './compositions/Main';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Main"
      component={Main}
      durationInFrames={300}
      fps={60}
      width={1920}
      height={1080}
    />
  );
};
