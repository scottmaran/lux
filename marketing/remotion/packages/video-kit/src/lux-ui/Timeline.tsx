import React from 'react';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import {TimelineEvent} from './TimelineEvent';
import type {DashboardTimelineEvent} from './types';

export type TimelineProps = {
  events: DashboardTimelineEvent[];
  incomingEvents?: DashboardTimelineEvent[];
  blend?: number;
  selectedRunName: string;
  title?: string;
  showAutoRefresh?: boolean;
  autoRefreshLabel?: string;
  theme?: Partial<LuxUiTheme>;
};

const EventList: React.FC<{events: DashboardTimelineEvent[]; theme: LuxUiTheme}> = ({events, theme}) => {
  return (
    <div
      style={{
        borderTop: `1px solid ${theme.border}`,
        maxHeight: 520,
        overflow: 'hidden',
      }}
    >
      {events.map((event, index) => (
        <TimelineEvent key={`${event.timestamp}-${event.target}-${index}`} event={event} theme={theme} />
      ))}
    </div>
  );
};

export const Timeline: React.FC<TimelineProps> = ({
  events,
  incomingEvents,
  blend = 0,
  selectedRunName,
  title = 'Timeline',
  showAutoRefresh = true,
  autoRefreshLabel = 'Auto-refresh active',
  theme,
}) => {
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};
  const hasBlend = incomingEvents && blend > 0;

  return (
    <div
      style={{
        backgroundColor: palette.surface,
        border: `1px solid ${palette.border}`,
        borderRadius: 12,
        overflow: 'hidden',
        height: 640,
      }}
    >
      <div
        style={{
          padding: '16px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: `1px solid ${palette.border}`,
        }}
      >
        <div>
          <div style={{fontSize: 24, fontWeight: 600, color: palette.text}}>{title}</div>
          <div style={{fontSize: 14, color: palette.mutedText, marginTop: 4}}>
            {events.length} events - Filtered by {selectedRunName}
          </div>
        </div>
        {showAutoRefresh ? (
          <div style={{display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: palette.mutedText}}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 999,
                backgroundColor: '#22C55E',
              }}
            />
            {autoRefreshLabel}
          </div>
        ) : null}
      </div>

      <div style={{position: 'relative'}}>
        <div style={{opacity: 1 - blend}}>
          <EventList events={events} theme={palette} />
        </div>
        {hasBlend ? (
          <div style={{position: 'absolute', inset: 0, opacity: blend}}>
            <EventList events={incomingEvents} theme={palette} />
          </div>
        ) : null}
      </div>
    </div>
  );
};
