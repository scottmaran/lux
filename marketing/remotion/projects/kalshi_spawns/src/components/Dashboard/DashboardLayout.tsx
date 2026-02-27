import React from 'react';
import {AbsoluteFill} from 'remotion';
import {colors} from '../../config/colors';
import {interFontFamily} from '../../config/fonts';
import type {DashboardMetrics, DashboardRun, DashboardTimelineEvent} from '../../config/terminalContent';
import {StatsBar} from './StatsBar';
import {FilterBar} from './FilterBar';
import {Timeline} from './Timeline';
import {RunsPanel} from './RunsPanel';

type DashboardLayoutProps = {
  metrics: DashboardMetrics;
  runs: DashboardRun[];
  selectedRunId: string;
  events: DashboardTimelineEvent[];
  incomingEvents?: DashboardTimelineEvent[];
  timelineBlend?: number;
  pulseRunId?: string;
  opacity?: number;
  scale?: number;
};

const getRunLabel = (runs: DashboardRun[], runId: string): string => {
  const run = runs.find((entry) => entry.id === runId);
  return run?.name ?? runId;
};

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  metrics,
  runs,
  selectedRunId,
  events,
  incomingEvents,
  timelineBlend = 0,
  pulseRunId,
  opacity = 1,
  scale = 1,
}) => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.dashboardBg,
        fontFamily: interFontFamily,
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: 'center center',
      }}
    >
      <div style={{padding: '24px 36px', display: 'flex', flexDirection: 'column', gap: 16}}>
        <header
          style={{
            backgroundColor: '#FFFFFF',
            border: '1px solid #E5E7EB',
            borderRadius: 12,
            padding: '16px 18px',
          }}
        >
          <div style={{fontSize: 34, fontWeight: 700, color: '#111827'}}>Lasso</div>
          <div style={{fontSize: 15, color: '#6B7280', marginTop: 4}}>
            The black box for your AI agents
          </div>
          <div style={{fontSize: 15, color: '#6B7280', marginTop: 2}}>
            A dedicated harness for OS-level tracking of everything your agents do
          </div>
        </header>

        <StatsBar metrics={metrics} />
        <FilterBar selectedTimeRange="1 hour" />

        <div style={{display: 'grid', gridTemplateColumns: '1.85fr 1fr', gap: 16}}>
          <Timeline
            events={events}
            incomingEvents={incomingEvents}
            blend={timelineBlend}
            selectedRunName={getRunLabel(runs, selectedRunId)}
          />
          <RunsPanel runs={runs} selectedRunId={selectedRunId} pulseRunId={pulseRunId} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
