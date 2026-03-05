import React from 'react';
import type {DashboardTimelineEvent} from '../../config/terminalContent';
import {TimelineEvent} from './TimelineEvent';

type TimelineProps = {
  events: DashboardTimelineEvent[];
  incomingEvents?: DashboardTimelineEvent[];
  blend?: number;
  selectedRunName: string;
};

const EventList: React.FC<{events: DashboardTimelineEvent[]}> = ({events}) => {
  return (
    <div
      style={{
        borderTop: '1px solid #E5E7EB',
        maxHeight: 520,
        overflow: 'hidden',
      }}
    >
      {events.map((event, index) => (
        <TimelineEvent key={`${event.timestamp}-${event.target}-${index}`} event={event} />
      ))}
    </div>
  );
};

export const Timeline: React.FC<TimelineProps> = ({
  events,
  incomingEvents,
  blend = 0,
  selectedRunName,
}) => {
  const hasBlend = incomingEvents && blend > 0;

  return (
    <div
      style={{
        backgroundColor: '#FFFFFF',
        border: '1px solid #E5E7EB',
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
          borderBottom: '1px solid #E5E7EB',
        }}
      >
        <div>
          <div style={{fontSize: 24, fontWeight: 600, color: '#111827'}}>Timeline</div>
          <div style={{fontSize: 14, color: '#6B7280', marginTop: 4}}>
            {events.length} events - Filtered by {selectedRunName}
          </div>
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#6B7280'}}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 999,
              backgroundColor: '#22C55E',
            }}
          />
          Auto-refresh active
        </div>
      </div>

      <div style={{position: 'relative'}}>
        <div style={{opacity: 1 - blend}}>
          <EventList events={events} />
        </div>
        {hasBlend ? (
          <div style={{position: 'absolute', inset: 0, opacity: blend}}>
            <EventList events={incomingEvents} />
          </div>
        ) : null}
      </div>
    </div>
  );
};
