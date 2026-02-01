import { useState } from 'react';
import { Timeline } from './components/Timeline';
import { RunsList } from './components/RunsList';
import { SummaryMetrics } from './components/SummaryMetrics';
import { FilterControls } from './components/FilterControls';

export type Source = 'audit' | 'ebpf';
export type TimeRange = '15m' | '1h' | '24h' | '7d';

export interface TimelineEvent {
  ts: string;
  event_type: string;
  source: Source;
  session_id?: string;
  job_id?: string;
  comm?: string;
  pid?: number;
  details?: Record<string, any>;
}

export interface Run {
  id: string;
  type: 'session' | 'job';
  mode?: string;
  status?: string;
  exit_code?: number;
  started_at?: string;
  ended_at?: string;
}

function App() {
  const [selectedSources, setSelectedSources] = useState<Source[]>(['audit', 'ebpf']);
  const [timeRange, setTimeRange] = useState<TimeRange>('1h');
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="px-6 py-4">
          <h1 className="text-xl font-semibold text-gray-900">Agent Harness</h1>
          <p className="text-sm text-gray-500 mt-1">Verifiability & Auditability for your AI agents</p>
          <p className="text-sm text-gray-500 mt-1">OS-level tracking of every call or change your agents make</p>
        </div>
      </header>

      {/* Main Content */}
      <div className="px-6 py-6 space-y-6">
        {/* Summary Metrics */}
        <SummaryMetrics
          selectedSources={selectedSources}
          timeRange={timeRange}
          selectedRun={selectedRun}
        />

        {/* Filter Controls */}
        <FilterControls
          selectedSources={selectedSources}
          onSourcesChange={setSelectedSources}
          timeRange={timeRange}
          onTimeRangeChange={setTimeRange}
        />

        {/* Split Content: Timeline + Runs */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline - Takes 2 columns */}
          <div className="lg:col-span-2">
            <Timeline
              selectedSources={selectedSources}
              timeRange={timeRange}
              selectedRun={selectedRun}
            />
          </div>

          {/* Runs List - Takes 1 column */}
          <div className="lg:col-span-1">
            <RunsList
              selectedRun={selectedRun}
              onSelectRun={setSelectedRun}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
