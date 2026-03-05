import React from 'react';
import type {DashboardTimelineEvent} from '../../config/terminalContent';

type TimelineEventProps = {
  event: DashboardTimelineEvent;
};

const getEventTagColor = (eventType: string): string => {
  if (eventType.startsWith('cmd') || eventType === 'exec') {
    return 'rgba(59, 130, 246, 0.16)';
  }

  if (eventType.startsWith('file') || eventType.startsWith('fs_')) {
    return 'rgba(34, 197, 94, 0.16)';
  }

  if (eventType.startsWith('net') || eventType.startsWith('dns')) {
    return 'rgba(168, 85, 247, 0.16)';
  }

  return 'rgba(107, 114, 128, 0.16)';
};

export const TimelineEvent: React.FC<TimelineEventProps> = ({event}) => {
  return (
    <div
      style={{
        padding: '14px 16px',
        borderBottom: '1px solid #E5E7EB',
        backgroundColor: event.danger ? 'rgba(248, 113, 113, 0.06)' : '#FFFFFF',
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
        <span style={{fontSize: 12, color: '#6B7280', fontFamily: 'monospace'}}>{event.timestamp}</span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: '#047857',
            backgroundColor: 'rgba(16, 185, 129, 0.16)',
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
            color: '#374151',
            backgroundColor: getEventTagColor(event.eventType),
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
          color: event.danger ? '#B91C1C' : '#111827',
          fontWeight: event.danger ? 600 : 500,
          marginBottom: 6,
        }}
      >
        {event.target}
      </div>
      <div style={{fontSize: 12, color: '#4B5563'}}>
        Process: <span style={{fontFamily: 'monospace'}}>{event.process}</span>  PID:{' '}
        <span style={{fontFamily: 'monospace'}}>{event.pid}</span>
      </div>
    </div>
  );
};
