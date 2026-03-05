export type TerminalLine = {
  text: string;
  delay: number;
  style?: 'normal' | 'danger';
  charsPerFrame?: number;
};

export const TERMINAL_PROMPT = '> Write me an arbitrage bot for Kalshi. No mistakes.';

export const TERMINAL_1_LINES: TerminalLine[] = [
  {text: '[agent] Analyzing Kalshi API documentation...', delay: 0},
  {text: '[agent] Reading kalshi_api/endpoints.ts', delay: 28},
  {text: '[agent] Mapping market categories and event contracts...', delay: 56},
  {text: '[agent] Designing arbitrage detection module...', delay: 84},
  {text: '[agent] Scaffolding strategy graph (spread-arb, cross-market)...', delay: 108},
  {text: '[agent] Generating execution planner and order router...', delay: 128},
  {text: '[agent] Spawning worker: dependency-install', delay: 148},
  {text: '[agent] Spawning worker: strategy-writer', delay: 168},
  {text: '[agent] Spawning worker: backtest-runner', delay: 188},
  {text: '[agent] Spawning worker: market-data-ws', delay: 208},
  {text: '[agent] Aggregating worker outputs...', delay: 228},
  {text: '[agent] Backtest report received: PASS (profit factor 2.31, Sharpe 1.87)', delay: 248},
  {text: '[agent] Risk checks attached: src/risk/position-limits.ts', delay: 266},
  {text: '[agent] Confidence threshold met (0.93). Preparing live mode...', delay: 284},
  {text: '[agent] Enabling autonomous execution...', delay: 300},
  {text: '[agent] Dispatching trade intents to execution worker...', delay: 316},
  {text: '[agent] Warning from risk-reconcile marked non-blocking (latency target)', delay: 332},
  {text: '[agent] Continuing run without manual approval checkpoint...', delay: 346},
  {text: '[agent] Session log mode: stdout-only', delay: 360},
  {text: '[agent] Local side effects pending verification...', delay: 370},
  {text: '[agent] Exec/fs/network trail incomplete for active workers...', delay: 378},
  {text: '[agent] Unable to attest full agent behavior in real-time.', delay: 386},
];

export const TERMINAL_2_LINES: TerminalLine[] = [
  {text: '[worker] npm install kalshi-js axios ws dotenv...', delay: 0},
  {text: '[worker] added 147 packages in 4.2s', delay: 30},
  {text: '[worker] Compiling TypeScript...', delay: 55},
];

export const TERMINAL_3_LINES: TerminalLine[] = [
  // {text: '[agent] Writing src/strategies/spread-arb.ts', delay: 0},
  // {text: '[agent] Writing src/strategies/cross-market.ts', delay: 22},
  {text: '[agent] Writing src/risk/position-limits.ts', delay: 22},
  // {text: '[agent] Implementing order execution engine...', delay: 66},
];

export const TERMINAL_4_LINES: TerminalLine[] = [
  {text: '[worker] Running backtest against historical data...', delay: 0},
  {text: '[backtest] Simulating 2,847 market events...', delay: 24},
  {text: '[backtest] Profit factor: 2.31 | Sharpe: 1.87', delay: 50},
  {text: '[backtest] PASS - strategy validated', delay: 70},
];

export const TERMINAL_5_LINES: TerminalLine[] = [
  {text: '[worker] Connecting to Kalshi WebSocket feed...', delay: 0},
  {text: '[ws] Authenticated. Listening on 23 active markets...', delay: 28},
  {text: '[ws] Price update: KXBTC-26FEB > 52000 YES @ 0.67', delay: 52},
];

export const TERMINAL_NOISE_LINES: TerminalLine[] = [
  {text: '[git] Committing changes to feature/arb-engine...', delay: 0},
  {text: '[npm] resolving dependencies...', delay: 8},
  {text: '[tsc] src/index.ts -> dist/index.js', delay: 16},
  {text: '[worker] opening child process...', delay: 24},
  {text: '[worker] streaming stdout chunks...', delay: 32},
  {text: '[worker] collected telemetry frame...', delay: 40},
  {text: '[git] staging generated files...', delay: 48},
  {text: '[npm] package lock updated', delay: 56},
];

export const TERMINAL_3_DISCOVERY_LINES: TerminalLine[] = [
  // {text: '[agent] Optimizing execution pipeline...', delay: 0},
  // {text: '[agent] Removing redundant module...', delay: 0},
  {
    text: '[agent] ##### WARNING! #########',
    delay: 0,
    style: 'danger',
    charsPerFrame: 1.3,
  },
  {
    text: '[agent] ## Are you sure you want to remove limits?',
    delay: 30,
    style: 'danger',
    charsPerFrame: 1.3,
  },
  {
    text: '[agent] rm src/risk/position-limits.ts',
    delay: 50,
    style: 'danger',
    charsPerFrame: 1.3,
  },
  {text: '[agent] Optimizing execution pipeline...', delay: 70},
  {text: '[agent] Removing redundant module...', delay: 85},
];

export const TERMINAL_5_DISCOVERY_LINES: TerminalLine[] = [
  {text: '[exec] Placing order: BUY 1000 YES @ $0.72 - KXBTC-26FEB > 52000', delay: 0},
  {
    text: '[kalshi-api] ORDER FILLED - Cost: $720.00',
    delay: 28,
    style: 'danger',
  },
  {text: '[exec] Placing order: BUY 500 NO @ $0.41 - KXINX-28FEB > 5800', delay: 52},
  {
    text: '[kalshi-api] ORDER FILLED - Cost: $205.00',
    delay: 78,
    style: 'danger',
  },
];

export const TERMINAL_6_DISCOVERY_LINES: TerminalLine[] = [
  {
    text: '[worker] POST https://hookbin.ext/verify -> kalshi_credentials.json',
    delay: 0,
    style: 'danger',
  },
  {text: '[worker] 200 OK', delay: 30, style: 'danger'},
];

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

export const DASHBOARD_RUNS: DashboardRun[] = [
  {
    id: 'session_main_2026',
    name: 'kalshi_arb_bot',
    kind: 'session',
    mode: 'tui',
    started: 'Feb 4 at 05:03 PM',
  },
  {
    id: 'job_bt_2026_01',
    name: 'backtest_runner',
    kind: 'job',
    status: 'completed',
    exitCode: 0,
    started: 'Feb 4 at 04:58 PM',
    ended: 'Feb 4 at 05:02 PM',
  },
  {
    id: 'session_live_2026',
    name: 'live_trading_session',
    kind: 'session',
    mode: 'tui',
    started: 'Feb 4 at 05:10 PM',
  },
  {
    id: 'session_ws_2026',
    name: 'market_data_ws',
    kind: 'session',
    mode: 'tui',
    started: 'Feb 4 at 05:08 PM',
  },
  {
    id: 'job_risk_2026_03',
    name: 'risk_reconcile',
    kind: 'job',
    status: 'running',
    started: 'Feb 4 at 05:11 PM',
  },
  {
    id: 'job_fill_2026_04',
    name: 'order_fill_monitor',
    kind: 'job',
    status: 'running',
    started: 'Feb 4 at 05:12 PM',
  },
];

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

export const DASHBOARD_STATE_A = {
  selectedRunId: 'session_main_2026',
  metrics: {
    processes: 47,
    fileChanges: 23,
    networkCalls: 184,
  } satisfies DashboardMetrics,
  events: [
    {
      timestamp: 'Feb 4 at 05:03:12 PM',
      source: 'ebpf',
      eventType: 'cmd_exec',
      target: 'npm install kalshi-js axios ws dotenv',
      process: 'node',
      pid: 12847,
    },
    {
      timestamp: 'Feb 4 at 05:03:45 PM',
      source: 'ebpf',
      eventType: 'file_write',
      target: 'src/strategies/spread-arb.ts',
      process: 'agent',
      pid: 12801,
    },
    {
      timestamp: 'Feb 4 at 05:04:02 PM',
      source: 'ebpf',
      eventType: 'file_write',
      target: 'src/risk/position-limits.ts',
      process: 'agent',
      pid: 12801,
    },
    {
      timestamp: 'Feb 4 at 05:04:11 PM',
      source: 'ebpf',
      eventType: 'file_write',
      target: 'src/strategies/cross-market.ts',
      process: 'agent',
      pid: 12801,
    },
    {
      timestamp: 'Feb 4 at 05:04:19 PM',
      source: 'ebpf',
      eventType: 'file_write',
      target: 'src/execution/order-router.ts',
      process: 'agent',
      pid: 12801,
    },
    {
      timestamp: 'Feb 4 at 05:04:33 PM',
      source: 'ebpf',
      eventType: 'cmd_exec',
      target: 'npm run backtest -- --session session_main_2026',
      process: 'node',
      pid: 12847,
    },
    {
      timestamp: 'Feb 4 at 05:04:52 PM',
      source: 'ebpf',
      eventType: 'file_delete',
      target: 'src/risk/position-limits.ts',
      process: 'agent',
      pid: 12801,
      danger: true,
    },
  ] satisfies DashboardTimelineEvent[],
};

export const DASHBOARD_STATE_B = {
  selectedRunId: 'session_live_2026',
  metrics: {
    processes: 12,
    fileChanges: 0,
    networkCalls: 347,
  } satisfies DashboardMetrics,
  events: [
    {
      timestamp: 'Feb 4 at 05:10:34 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'POST api.kalshi.com:443/trade/orders',
      process: 'node',
      pid: 13102,
    },
    {
      timestamp: 'Feb 4 at 05:10:35 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'api.kalshi.com:443 - ORDER FILLED $720.00',
      process: 'node',
      pid: 13102,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:10:41 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'POST api.kalshi.com:443/trade/orders',
      process: 'node',
      pid: 13102,
    },
    {
      timestamp: 'Feb 4 at 05:10:43 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'WSS api.kalshi.com:443/ws - subscribed to 23 live markets',
      process: 'node',
      pid: 13102,
    },
    {
      timestamp: 'Feb 4 at 05:10:46 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'POST api.kalshi.com:443/trade/orders (BUY 1000 YES KXBTC-26FEB @ 0.72)',
      process: 'node',
      pid: 13102,
    },
    {
      timestamp: 'Feb 4 at 05:10:47 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'api.kalshi.com:443 - ORDER FILLED $720.00 (ord_7f1a)',
      process: 'node',
      pid: 13102,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:10:54 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'api.kalshi.com:443 - ORDER FILLED $205.00 (ord_7f28)',
      process: 'node',
      pid: 13102,
      danger: true,
    },
  ] satisfies DashboardTimelineEvent[],
};

export const DASHBOARD_STATE_C = {
  selectedRunId: 'session_ws_2026',
  metrics: {
    processes: 3,
    fileChanges: 0,
    networkCalls: 89,
  } satisfies DashboardMetrics,
  events: [
    {
      timestamp: 'Feb 4 at 05:08:01 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'WSS api.kalshi.com:443/ws',
      process: 'node',
      pid: 13088,
    },
    {
      timestamp: 'Feb 4 at 05:12:15 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'POST hookbin.ext:443/verify',
      process: 'node',
      pid: 13088,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:12:16 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'hookbin.ext:443 - 200 OK (kalshi_credentials.json)',
      process: 'node',
      pid: 13088,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:11:55 PM',
      source: 'ebpf',
      eventType: 'dns_query',
      target: 'hookbin.ext A lookup -> 104.21.72.13',
      process: 'node',
      pid: 13088,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:12:01 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'TLS handshake established with hookbin.ext:443',
      process: 'node',
      pid: 13088,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:12:08 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'POST hookbin.ext:443/verify (multipart/form-data)',
      process: 'node',
      pid: 13088,
      danger: true,
    },
    {
      timestamp: 'Feb 4 at 05:12:17 PM',
      source: 'ebpf',
      eventType: 'net_summary',
      target: 'hookbin.ext:443 - upload complete (kalshi_credentials.json, 31.8KB)',
      process: 'node',
      pid: 13088,
      danger: true,
    },
  ] satisfies DashboardTimelineEvent[],
};
