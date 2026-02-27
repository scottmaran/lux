import React from 'react';
import {AbsoluteFill} from 'remotion';
import {FilterBar} from './FilterBar';
import {RunsPanel} from './RunsPanel';
import {StatsBar} from './StatsBar';
import {DEFAULT_LUX_UI_THEME, type LuxUiTheme} from './theme';
import {Timeline} from './Timeline';
import type {DashboardMetrics, DashboardRun, DashboardTimeRange, DashboardTimelineEvent} from './types';

export type DashboardLayoutProps = {
  metrics: DashboardMetrics;
  runs: DashboardRun[];
  selectedRunId: string;
  events: DashboardTimelineEvent[];
  incomingEvents?: DashboardTimelineEvent[];
  timelineBlend?: number;
  pulseRunId?: string;
  opacity?: number;
  scale?: number;
  fontFamily?: string;
  title?: string;
  subtitle?: string;
  description?: string;
  selectedTimeRange?: DashboardTimeRange;
  timeRanges?: DashboardTimeRange[];
  dataSources?: string[];
  activeDataSources?: string[];
  showAutoRefresh?: boolean;
  autoRefreshLabel?: string;
  theme?: Partial<LuxUiTheme>;
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
  fontFamily,
  title = 'Lasso',
  subtitle = 'The black box for your AI agents',
  description = 'A dedicated harness for OS-level tracking of everything your agents do',
  selectedTimeRange = '1 hour',
  timeRanges,
  dataSources,
  activeDataSources,
  showAutoRefresh = true,
  autoRefreshLabel,
  theme,
}) => {
  const palette = {...DEFAULT_LUX_UI_THEME, ...theme};

  return (
    <AbsoluteFill
      style={{
        backgroundColor: palette.dashboardBg,
        fontFamily,
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: 'center center',
      }}
    >
      <div style={{padding: '24px 36px', display: 'flex', flexDirection: 'column', gap: 16}}>
        <header
          style={{
            backgroundColor: palette.surface,
            border: `1px solid ${palette.border}`,
            borderRadius: 12,
            padding: '16px 18px',
          }}
        >
          <div style={{fontSize: 34, fontWeight: 700, color: palette.text}}>{title}</div>
          <div style={{fontSize: 15, color: palette.mutedText, marginTop: 4}}>{subtitle}</div>
          <div style={{fontSize: 15, color: palette.mutedText, marginTop: 2}}>{description}</div>
        </header>

        <StatsBar metrics={metrics} theme={palette} />
        <FilterBar
          selectedTimeRange={selectedTimeRange}
          timeRanges={timeRanges}
          dataSources={dataSources}
          activeDataSources={activeDataSources}
          theme={palette}
        />

        <div style={{display: 'grid', gridTemplateColumns: '1.85fr 1fr', gap: 16}}>
          <Timeline
            events={events}
            incomingEvents={incomingEvents}
            blend={timelineBlend}
            selectedRunName={getRunLabel(runs, selectedRunId)}
            showAutoRefresh={showAutoRefresh}
            autoRefreshLabel={autoRefreshLabel}
            theme={palette}
          />
          <RunsPanel runs={runs} selectedRunId={selectedRunId} pulseRunId={pulseRunId} theme={palette} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
