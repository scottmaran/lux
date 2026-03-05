import React from 'react';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import type {DashboardMetrics} from './types';

export type StatsBarProps = {
  metrics: DashboardMetrics;
  typographyScale?: number;
  theme?: Partial<LuxUiTheme>;
};

const cardStyle: React.CSSProperties = {
  borderRadius: 12,
  padding: '16px 18px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

export const StatsBar: React.FC<StatsBarProps> = ({metrics, typographyScale = 1, theme}) => {
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};
  const textSize = (value: number): number => Math.round(value * typographyScale);

  const cards = [
    {
      label: 'Processes',
      value: metrics.processes.toLocaleString(),
      color: palette.primaryBlue,
      bg: palette.primaryBlueSoft,
      glyph: 'P',
    },
    {
      label: 'File Changes',
      value: metrics.fileChanges.toLocaleString(),
      color: palette.successGreen,
      bg: palette.successGreenSoft,
      glyph: 'F',
    },
    {
      label: 'Network Calls',
      value: metrics.networkCalls.toLocaleString(),
      color: palette.accentPurple,
      bg: palette.accentPurpleSoft,
      glyph: 'N',
    },
  ];

  return (
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16}}>
      {cards.map((card) => (
        <div
          key={card.label}
          style={{
            ...cardStyle,
            backgroundColor: palette.surface,
            border: `1px solid ${palette.border}`,
          }}
        >
          <div>
            <div style={{fontSize: textSize(15), color: palette.mutedText, marginBottom: 6}}>{card.label}</div>
            <div style={{fontSize: textSize(36), lineHeight: 1, fontWeight: 700, color: palette.text}}>{card.value}</div>
          </div>
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 10,
              color: card.color,
              backgroundColor: card.bg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: textSize(16),
              fontWeight: 700,
            }}
          >
            {card.glyph}
          </div>
        </div>
      ))}
    </div>
  );
};
