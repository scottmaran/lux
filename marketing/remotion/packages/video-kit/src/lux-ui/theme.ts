export type LuxUiTheme = {
  dashboardBg: string;
  surface: string;
  border: string;
  text: string;
  mutedText: string;
  secondaryText: string;
  rowText: string;
  dangerText: string;
  primaryBlue: string;
  primaryBlueSoft: string;
  successGreen: string;
  successGreenSoft: string;
  accentPurple: string;
  accentPurpleSoft: string;
  sourceBadgeText: string;
  sourceBadgeBg: string;
};

export const DEFAULT_LUX_UI_THEME: LuxUiTheme = {
  dashboardBg: '#F9FAFB',
  surface: '#FFFFFF',
  border: '#E5E7EB',
  text: '#111827',
  mutedText: '#6B7280',
  secondaryText: '#374151',
  rowText: '#4B5563',
  dangerText: '#B91C1C',
  primaryBlue: '#2563EB',
  primaryBlueSoft: 'rgba(59, 130, 246, 0.16)',
  successGreen: '#16A34A',
  successGreenSoft: 'rgba(34, 197, 94, 0.16)',
  accentPurple: '#9333EA',
  accentPurpleSoft: 'rgba(168, 85, 247, 0.16)',
  sourceBadgeText: '#047857',
  sourceBadgeBg: 'rgba(16, 185, 129, 0.16)',
};
