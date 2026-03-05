import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {
  DashboardLayout,
  type DashboardMetrics,
  type DashboardRun,
  type DashboardTimelineEvent,
} from '../../../../packages/video-kit/src';

const runs: DashboardRun[] = [
  {
    id: 'session_main',
    name: 'lux_monitor_session',
    kind: 'session',
    mode: 'tui',
    started: 'Feb 27 at 09:10 AM',
  },
  {
    id: 'job_bootstrap',
    name: 'bootstrap_worker',
    kind: 'job',
    status: 'completed',
    exitCode: 0,
    started: 'Feb 27 at 09:05 AM',
    ended: 'Feb 27 at 09:06 AM',
  },
  {
    id: 'session_network',
    name: 'network_watch',
    kind: 'session',
    mode: 'api',
    started: 'Feb 27 at 09:11 AM',
  },
  {
    id: 'job_alerting',
    name: 'alert_dispatch',
    kind: 'job',
    status: 'running',
    started: 'Feb 27 at 09:13 AM',
  },
];

const metricsA: DashboardMetrics = {
  processes: 42,
  fileChanges: 18,
  networkCalls: 129,
};

const metricsB: DashboardMetrics = {
  processes: 48,
  fileChanges: 22,
  networkCalls: 173,
};

const eventsA: DashboardTimelineEvent[] = [
  {
    timestamp: '09:10:12',
    source: 'ebpf',
    eventType: 'cmd_exec',
    target: 'npm run bootstrap-monitor',
    process: 'node',
    pid: 4217,
  },
  {
    timestamp: '09:10:24',
    source: 'ebpf',
    eventType: 'file_write',
    target: 'logs/session/index.jsonl',
    process: 'agent',
    pid: 4192,
  },
  {
    timestamp: '09:10:39',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'POST api.provider.example/runs',
    process: 'node',
    pid: 4217,
  },
  {
    timestamp: '09:10:49',
    source: 'ebpf',
    eventType: 'file_delete',
    target: 'src/risk/position-limits.ts',
    process: 'agent',
    pid: 4192,
    danger: true,
  },
];

const eventsB: DashboardTimelineEvent[] = [
  {
    timestamp: '09:11:06',
    source: 'ebpf',
    eventType: 'cmd_exec',
    target: 'python scripts/reconcile.py --session session_main',
    process: 'python',
    pid: 4312,
  },
  {
    timestamp: '09:11:23',
    source: 'ebpf',
    eventType: 'net_summary',
    target: 'PUT api.provider.example/runs/session_main/checkpoint',
    process: 'python',
    pid: 4312,
  },
  {
    timestamp: '09:11:34',
    source: 'ebpf',
    eventType: 'file_write',
    target: 'logs/session/checkpoints/09-11-34.json',
    process: 'agent',
    pid: 4192,
  },
  {
    timestamp: '09:11:47',
    source: 'ebpf',
    eventType: 'dns_query',
    target: 'resolve telemetry.lux.dev',
    process: 'python',
    pid: 4312,
  },
];

export const LuxUiShowcase: React.FC = () => {
  const frame = useCurrentFrame();

  const transitionStart = 110;
  const transitionEnd = 170;

  const blend = interpolate(frame, [transitionStart, transitionEnd], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const isSecondState = frame >= transitionEnd;

  return (
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(circle at 80% 15%, rgba(56, 189, 248, 0.25), transparent 34%), radial-gradient(circle at 20% 80%, rgba(34, 197, 94, 0.20), transparent 32%), #0b1120',
        padding: 48,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 76,
          top: 30,
          color: '#DBEAFE',
          fontSize: 34,
          fontWeight: 700,
          letterSpacing: 0.5,
        }}
      >
        Video Kit Lux UI Showcase
      </div>

      <div
        style={{
          position: 'absolute',
          inset: '86px 64px 40px 64px',
          borderRadius: 22,
          overflow: 'hidden',
          border: '1px solid rgba(255, 255, 255, 0.16)',
          boxShadow: '0 18px 45px rgba(0, 0, 0, 0.35)',
        }}
      >
        <DashboardLayout
          metrics={isSecondState ? metricsB : metricsA}
          runs={runs}
          selectedRunId={isSecondState ? 'session_network' : 'session_main'}
          events={eventsA}
          incomingEvents={eventsB}
          timelineBlend={blend}
          pulseRunId={isSecondState ? 'session_network' : 'session_main'}
          title="Lasso"
          subtitle="Visual QA for reusable dashboard primitives"
          description="This composition validates spacing, color, and animation behavior for the shared Lux UI kit."
          selectedTimeRange="1 hour"
          activeDataSources={['Commands', 'Network']}
          showAutoRefresh
          autoRefreshLabel="Live updates simulated"
          fontFamily="Inter, ui-sans-serif, system-ui"
        />
      </div>
    </AbsoluteFill>
  );
};
