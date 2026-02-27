import React from 'react';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import type {DashboardTimeRange} from './types';

export type FilterBarProps = {
  selectedTimeRange: DashboardTimeRange;
  timeRanges?: DashboardTimeRange[];
  dataSources?: string[];
  activeDataSources?: string[];
  theme?: Partial<LuxUiTheme>;
};

export const FilterBar: React.FC<FilterBarProps> = ({
  selectedTimeRange,
  timeRanges = ['15 min', '1 hour', '24 hours', '7 days'],
  dataSources = ['Commands', 'Network'],
  activeDataSources,
  theme,
}) => {
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};
  const selectedSources = new Set(activeDataSources ?? dataSources);

  return (
    <div
      style={{
        backgroundColor: palette.surface,
        border: `1px solid ${palette.border}`,
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        justifyContent: 'space-between',
      }}
    >
      <div>
        <div style={{fontSize: 14, color: palette.secondaryText, fontWeight: 600, marginBottom: 8}}>
          Data Source
        </div>
        <div style={{display: 'flex', gap: 8}}>
          {dataSources.map((source) => {
            const selected = selectedSources.has(source);
            return (
              <button
                key={source}
                type="button"
                style={{
                  borderRadius: 8,
                  border: 0,
                  backgroundColor: selected ? palette.primaryBlue : palette.border,
                  color: selected ? '#FFFFFF' : palette.secondaryText,
                  fontSize: 14,
                  fontWeight: 600,
                  padding: '8px 14px',
                }}
              >
                {source}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div style={{fontSize: 14, color: palette.secondaryText, fontWeight: 600, marginBottom: 8}}>
          Time Range
        </div>
        <div style={{display: 'flex', gap: 8}}>
          {timeRanges.map((range) => {
            const selected = range === selectedTimeRange;
            return (
              <button
                key={range}
                type="button"
                style={{
                  borderRadius: 8,
                  border: 0,
                  backgroundColor: selected ? palette.successGreen : palette.border,
                  color: selected ? '#FFFFFF' : palette.secondaryText,
                  fontSize: 14,
                  fontWeight: 600,
                  padding: '8px 14px',
                }}
              >
                {range}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
