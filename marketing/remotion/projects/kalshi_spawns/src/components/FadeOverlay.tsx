import React from 'react';
import {AbsoluteFill} from 'remotion';
import {colors} from '../config/colors';
import {interFontFamily} from '../config/fonts';

type FadeOverlayProps = {
  opacity: number;
  text?: string;
  textOpacity?: number;
  textY?: number;
};

export const FadeOverlay: React.FC<FadeOverlayProps> = ({
  opacity,
  text,
  textOpacity = 1,
  textY = 0,
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.overlayBg,
        opacity,
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      {text ? (
        <div
          style={{
            fontFamily: interFontFamily,
            fontSize: 48,
            fontWeight: 600,
            color: colors.overlayText,
            textAlign: 'center',
            opacity: textOpacity,
            transform: `translateY(${textY}px)`,
          }}
        >
          {text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
