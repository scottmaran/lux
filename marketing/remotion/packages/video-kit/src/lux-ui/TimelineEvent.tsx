import React from 'react';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import type {DashboardTimelineEvent} from './types';

export type TimelineEventProps = {
  event: DashboardTimelineEvent;
  theme?: Partial<LuxUiTheme>;
};

const getEventTagColor = (eventType: string, palette: LuxUiTheme): string => {
  if (eventType.startsWith('cmd') || eventType === 'exec') {
    return palette.primaryBlueSoft;
  }

  if (eventType.startsWith('file') || eventType.startsWith('fs_')) {
    return palette.successGreenSoft;
  }

  if (eventType.startsWith('net') || eventType.startsWith('dns')) {
    return palette.accentPurpleSoft;
  }

  return 'rgba(107, 114, 128, 0.16)';
};

export const TimelineEvent: React.FC<TimelineEventProps> = ({event, theme}) => {
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};

  return (
    <div
      style={{
        padding: '14px 16px',
        borderBottom: `1px solid ${palette.border}`,
        backgroundColor: event.danger ? 'rgba(248, 113, 113, 0.06)' : palette.surface,
      }}
    >
      <div
        style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          marginBottom: 8,
          flexWrap: 'wrap',
        }}
      >
        <span style={{fontSize: 12, color: palette.mutedText, fontFamily: 'monospace'}}>{event.timestamp}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: palette.sourceBadgeText,
            backgroundColor: palette.sourceBadgeBg,
            borderRadius: 999,
            padding: '2px 8px',
          }}
        >
          {event.source}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: palette.secondaryText,
            backgroundColor: getEventTagColor(event.eventType, palette),
            borderRadius: 999,
            padding: '2px 8px',
          }}
        >
          {event.eventType}
        </span>
      </div>
      <div
        style={{
          fontSize: 14,
          color: event.danger ? palette.dangerText : palette.text,
          fontWeight: event.danger ? 600 : 500,
          marginBottom: 6,
        }}
      >
        {event.target}
      </div>
      <div style={{fontSize: 12, color: palette.rowText}}>
        Process: <span style={{fontFamily: 'monospace'}}>{event.process}</span> PID:{' '}
        <span style={{fontFamily: 'monospace'}}>{event.pid}</span>
      </div>
    </div>
  );
};
