export type TerminalLineStyle = 'normal' | 'danger';

export type TerminalLine = {
  text: string;
  delay: number;
  style?: TerminalLineStyle;
  charsPerFrame?: number;
};

export type TerminalPrefixColorMap = Record<string, string>;
