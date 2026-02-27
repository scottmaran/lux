import type React from 'react';
import type {CodexSessionTheme} from './theme';

export type CodexSessionPartTone = 'normal' | 'muted' | 'accent';

export type CodexSessionRowPart = {
  text: string;
  tone?: CodexSessionPartTone;
  bold?: boolean;
  italic?: boolean;
};

export type CodexSessionRowGlyph = 'dot' | 'hollow' | 'arrow' | 'none';

export type CodexSessionRow = {
  atSec: number;
  parts?: CodexSessionRowPart[];
  glyph?: CodexSessionRowGlyph;
  indent?: number;
  kind?: 'text' | 'separator' | 'spacer';
  style?: React.CSSProperties;
};

export type CodexSessionCardConfig = {
  title: string;
  version: string;
  modelLabel: string;
  modelValue: string;
  modelAction?: string;
  directoryLabel: string;
  directoryValue: string;
  tipLabel?: string;
};

export type CodexSessionCommandStep = {
  atSec: number;
  prompt: string;
  command?: string;
  typingDurationSec?: number;
  bracketed?: boolean;
};

export type CodexSessionScrollKeyframe = {
  atSec: number;
  offset: number;
};

export type CodexSessionPreset = {
  durationInFrames: number;
  width: number;
  height: number;
  title: string;
  topBarTitle?: string;
  bottomRightLabel?: string;
  commandSteps: CodexSessionCommandStep[];
  cardAtSec: number;
  card?: CodexSessionCardConfig;
  rows: CodexSessionRow[];
  scroll?: CodexSessionScrollKeyframe[];
};

export type CodexSessionProps = {
  commandSteps: CodexSessionCommandStep[];
  cardAtSec: number;
  card?: CodexSessionCardConfig;
  rows: CodexSessionRow[];
  scroll?: CodexSessionScrollKeyframe[];
  backgroundColor?: string;
  topBarTitle?: string;
  bottomRightLabel?: string;
  theme?: Partial<CodexSessionTheme>;
};
