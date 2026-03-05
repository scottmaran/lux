import React from 'react';

type FilterBarProps = {
  selectedTimeRange: '15 min' | '1 hour' | '24 hours' | '7 days';
};

const sourceButtonStyle: React.CSSProperties = {
  borderRadius: 8,
  border: 0,
  backgroundColor: '#2563EB',
  color: '#FFFFFF',
  fontSize: 14,
  fontWeight: 600,
  padding: '8px 14px',
};

export const FilterBar: React.FC<FilterBarProps> = ({selectedTimeRange}) => {
  const timeRanges: FilterBarProps['selectedTimeRange'][] = ['15 min', '1 hour', '24 hours', '7 days'];

  return (
    <div
      style={{
        backgroundColor: '#FFFFFF',
        border: '1px solid #E5E7EB',
        borderRadius: 12,
        padding: '16px 18px',
        display: 'flex',
        justifyContent: 'space-between',
      }}
    >
      <div>
        <div style={{fontSize: 14, color: '#374151', fontWeight: 600, marginBottom: 8}}>Data Source</div>
        <div style={{display: 'flex', gap: 8}}>
          <button type="button" style={sourceButtonStyle}>
            Commands
          </button>
          <button type="button" style={sourceButtonStyle}>
            Network
          </button>
        </div>
      </div>

      <div>
        <div style={{fontSize: 14, color: '#374151', fontWeight: 600, marginBottom: 8}}>Time Range</div>
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
                  backgroundColor: selected ? '#16A34A' : '#E5E7EB',
                  color: selected ? '#FFFFFF' : '#374151',
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
