import React from 'react';
import type {DashboardMetrics} from '../../config/terminalContent';

type StatsBarProps = {
  metrics: DashboardMetrics;
};

const cardStyle: React.CSSProperties = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E5E7EB',
  borderRadius: 12,
  padding: '16px 18px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

export const StatsBar: React.FC<StatsBarProps> = ({metrics}) => {
  const cards = [
    {
      label: 'Processes',
      value: metrics.processes.toLocaleString(),
      color: '#2563EB',
      bg: 'rgba(59, 130, 246, 0.16)',
      glyph: 'P',
    },
    {
      label: 'File Changes',
      value: metrics.fileChanges.toLocaleString(),
      color: '#16A34A',
      bg: 'rgba(34, 197, 94, 0.16)',
      glyph: 'F',
    },
    {
      label: 'Network Calls',
      value: metrics.networkCalls.toLocaleString(),
      color: '#9333EA',
      bg: 'rgba(168, 85, 247, 0.16)',
      glyph: 'N',
    },
  ];

  return (
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16}}>
      {cards.map((card) => (
        <div key={card.label} style={cardStyle}>
          <div>
            <div style={{fontSize: 15, color: '#6B7280', marginBottom: 6}}>{card.label}</div>
            <div style={{fontSize: 36, lineHeight: 1, fontWeight: 700, color: '#111827'}}>{card.value}</div>
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
