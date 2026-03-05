import React from 'react';
import {spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import type {DashboardRun} from './types';

export type RunsPanelProps = {
  runs: DashboardRun[];
  selectedRunId: string;
  pulseRunId?: string;
  title?: string;
  typographyScale?: number;
  theme?: Partial<LuxUiTheme>;
};

export const RunsPanel: React.FC<RunsPanelProps> = ({
  runs,
  selectedRunId,
  pulseRunId,
  title = 'Runs',
  typographyScale = 1,
  theme,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};
  const textSize = (value: number): number => Math.round(value * typographyScale);

  const kindStyles = {
    session: {
      backgroundColor: palette.accentPurpleSoft,
      color: '#7E22CE',
    },
    job: {
      backgroundColor: palette.primaryBlueSoft,
      color: '#1D4ED8',
    },
  } as const;

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
      <div style={{padding: '16px 18px', borderBottom: `1px solid ${palette.border}`}}>
        <div style={{fontSize: textSize(24), fontWeight: 600, color: palette.text}}>{title}</div>
        <div style={{fontSize: textSize(14), color: palette.mutedText, marginTop: 4}}>{runs.length} total</div>
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
                borderBottom: `1px solid ${palette.border}`,
                backgroundColor: selected
                  ? `rgba(59, 130, 246, ${0.12 + pulseProgress * 0.08})`
                  : palette.surface,
                borderLeft: selected ? `4px solid ${palette.primaryBlue}` : '4px solid transparent',
              }}
            >
              <div style={{display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6}}>
                <span
                  style={{
                    fontSize: textSize(11),
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: '2px 8px',
                    ...kindStyles[run.kind],
                  }}
                >
                  {run.kind}
                </span>
                <span style={{fontSize: textSize(14), fontWeight: 600, color: palette.text}}>{run.name}</span>
              </div>

              <div
                style={{
                  fontSize: textSize(12),
                  color: palette.mutedText,
                  fontFamily: 'monospace',
                  marginBottom: 4,
                }}
              >
                {run.id}
              </div>

              <div style={{fontSize: textSize(12), color: palette.rowText, marginBottom: 4}}>
                {run.mode
                  ? run.mode
                  : `${run.status ?? 'unknown'}${run.exitCode !== undefined ? ` (${run.exitCode})` : ''}`}
              </div>

              <div style={{fontSize: textSize(12), color: palette.mutedText}}>Started: {run.started}</div>
              {run.ended ? (
                <div style={{fontSize: textSize(12), color: palette.mutedText}}>Ended: {run.ended}</div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};
