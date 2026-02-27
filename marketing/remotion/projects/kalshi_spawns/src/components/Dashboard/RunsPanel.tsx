import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {DashboardRun} from '../../config/terminalContent';

type RunsPanelProps = {
  runs: DashboardRun[];
  selectedRunId: string;
  pulseRunId?: string;
};

const kindStyles = {
  session: {
    backgroundColor: 'rgba(168, 85, 247, 0.16)',
    color: '#7E22CE',
  },
  job: {
    backgroundColor: 'rgba(59, 130, 246, 0.16)',
    color: '#1D4ED8',
  },
} as const;

export const RunsPanel: React.FC<RunsPanelProps> = ({runs, selectedRunId, pulseRunId}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

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
      <div style={{padding: '16px 18px', borderBottom: '1px solid #E5E7EB'}}>
        <div style={{fontSize: 24, fontWeight: 600, color: '#111827'}}>Runs</div>
        <div style={{fontSize: 14, color: '#6B7280', marginTop: 4}}>{runs.length} total</div>
      </div>

      <div>
        {runs.map((run, index) => {
          const selected = run.id === selectedRunId;
          const pulse = run.id === pulseRunId;
          const pulseProgress = pulse
            ? spring({
                frame: frame - index * 2,
                fps,
                config: {damping: 20, stiffness: 180},
                durationInFrames: 20,
              })
            : 0;

          return (
            <div
              key={run.id}
              style={{
                padding: '12px 14px',
                borderBottom: '1px solid #E5E7EB',
                backgroundColor: selected
                  ? `rgba(59, 130, 246, ${0.12 + pulseProgress * 0.08})`
                  : '#FFFFFF',
                borderLeft: selected ? '4px solid #2563EB' : '4px solid transparent',
              }}
            >
              <div style={{display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6}}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: '2px 8px',
                    ...kindStyles[run.kind],
                  }}
                >
                  {run.kind}
                </span>
                <span style={{fontSize: 14, fontWeight: 600, color: '#111827'}}>{run.name}</span>
              </div>

              <div style={{fontSize: 12, color: '#6B7280', fontFamily: 'monospace', marginBottom: 4}}>
                {run.id}
              </div>

              <div style={{fontSize: 12, color: '#4B5563', marginBottom: 4}}>
                {run.mode ? run.mode : `${run.status ?? 'unknown'}${run.exitCode !== undefined ? ` (${run.exitCode})` : ''}`}
              </div>

              <div style={{fontSize: 12, color: '#6B7280'}}>Started: {run.started}</div>
              {run.ended ? <div style={{fontSize: 12, color: '#6B7280'}}>Ended: {run.ended}</div> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};
