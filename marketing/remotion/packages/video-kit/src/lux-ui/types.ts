export type DashboardRun = {
  id: string;
  name: string;
  kind: 'session' | 'job';
  mode?: string;
  status?: string;
  exitCode?: number;
  started: string;
  ended?: string;
};

export type DashboardMetrics = {
  processes: number;
  fileChanges: number;
  networkCalls: number;
};

export type DashboardTimelineEvent = {
  timestamp: string;
  source: string;
  eventType: string;
  target: string;
  process: string;
  pid: number;
  danger?: boolean;
};

export type DashboardTimeRange = '15 min' | '1 hour' | '24 hours' | '7 days' | string;
