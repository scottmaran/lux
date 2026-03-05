export type TerminalTheme = {
  terminalBg: string;
  terminalText: string;
  terminalGreen: string;
  terminalYellow: string;
  terminalRed: string;
  terminalCyan: string;
  terminalCursor: string;
  windowHeaderBg: string;
  windowHeaderBorder: string;
  windowBorder: string;
  windowFocusedBorder: string;
  windowShadow: string;
  windowFocusedShadow: string;
};

export const DEFAULT_TERMINAL_THEME: TerminalTheme = {
  terminalBg: '#1E1E2E',
  terminalText: '#CDD6F4',
  terminalGreen: '#A6E3A1',
  terminalYellow: '#F9E2AF',
  terminalRed: '#F38BA8',
  terminalCyan: '#7DD3FC',
  terminalCursor: '#CDD6F4',
  windowHeaderBg: '#27293D',
  windowHeaderBorder: '1px solid rgba(255, 255, 255, 0.06)',
  windowBorder: '1px solid rgba(255, 255, 255, 0.08)',
  windowFocusedBorder: '1px solid rgba(125, 211, 252, 0.5)',
  windowShadow: '0 14px 34px rgba(0, 0, 0, 0.45)',
  windowFocusedShadow: '0 0 0 1px rgba(125, 211, 252, 0.35), 0 16px 40px rgba(0, 0, 0, 0.5)',
};
