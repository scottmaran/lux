import type React from 'react';
import type {CodexSessionTheme} from './theme';

export type CodexSessionPartTone = 'normal' | 'muted' | 'accent';

export type CodexSessionRowPart = {
  text: string;
  tone?: CodexSessionPartTone;
  bold?: boolean;
  italic?: boolean;
  animation?: 'none' | 'scan-bold';
};

export type CodexSessionRowGlyph = 'dot' | 'hollow' | 'arrow' | 'none';

export type CodexSessionRow = {
  atSec: number;
  untilSec?: number;
  parts?: CodexSessionRowPart[];
  glyph?: CodexSessionRowGlyph;
  indent?: number;
  kind?: 'text' | 'separator' | 'spacer';
  animation?: 'none' | 'scan-bold';
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

export type CodexSessionRowPush = {
  atSec: number;
  offset: number;
  durationFrames?: number;
};

export type CodexSessionTopBarTitleStep = {
  atSec: number;
  title: string;
};

export type CodexSessionFooterLine = {
  glyph: string;
  text: string;
};

export type CodexSessionPreset = {
  durationInFrames: number;
  width: number;
  height: number;
  title: string;
  topBarTitle?: string;
  topBarTitleSteps?: CodexSessionTopBarTitleStep[];
  bottomRightLabel?: string;
  bottomRightAtSec?: number;
  commandSteps: CodexSessionCommandStep[];
  cardAtSec: number;
  card?: CodexSessionCardConfig;
  rows: CodexSessionRow[];
  scroll?: CodexSessionScrollKeyframe[];
  rowPushes?: CodexSessionRowPush[];
  footerAtSec?: number;
  footerInputAtSec?: number;
  footerLines?: CodexSessionFooterLine[];
};

export type CodexSessionProps = {
  commandSteps: CodexSessionCommandStep[];
  cardAtSec: number;
  card?: CodexSessionCardConfig;
  rows: CodexSessionRow[];
  scroll?: CodexSessionScrollKeyframe[];
  rowPushes?: CodexSessionRowPush[];
  backgroundColor?: string;
  topBarTitle?: string;
  topBarTitleSteps?: CodexSessionTopBarTitleStep[];
  bottomRightLabel?: string;
  bottomRightAtSec?: number;
  footerAtSec?: number;
  footerInputAtSec?: number;
  footerLines?: CodexSessionFooterLine[];
  theme?: Partial<CodexSessionTheme>;
};
