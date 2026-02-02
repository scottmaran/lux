import { useState, useEffect } from 'react';
import { Play, CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { Run } from '../App';

interface RunsListProps {
  selectedRun: Run | null;
  onSelectRun: (run: Run | null) => void;
}

export function RunsList({ selectedRun, onSelectRun }: RunsListProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRuns();
  }, []);

  const fetchRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch sessions and jobs in parallel
      const [sessionsRes, jobsRes] = await Promise.all([
        fetch('/api/sessions'),
        fetch('/api/jobs')
      ]);

      if (!sessionsRes.ok || !jobsRes.ok) {
        throw new Error('Failed to fetch runs');
      }

      const sessionsPayload = await sessionsRes.json();
      const jobsPayload = await jobsRes.json();

      const sessions = Array.isArray(sessionsPayload?.sessions) ? sessionsPayload.sessions : [];
      const jobs = Array.isArray(jobsPayload?.jobs) ? jobsPayload.jobs : [];

      // Merge and sort by started_at
      const allRuns: Run[] = [
        ...sessions.map((s: any) => ({
          id: s.session_id,
          type: 'session' as const,
          mode: s.mode,
          exit_code: s.exit_code,
          started_at: s.started_at,
          ended_at: s.ended_at
        })),
        ...jobs.map((j: any) => ({
          id: j.job_id,
          type: 'job' as const,
          status: j.status,
          exit_code: j.exit_code,
          started_at: j.started_at || j.submitted_at,
          ended_at: j.ended_at
        }))
      ].sort((a, b) =>
        new Date(b.started_at || 0).getTime() - new Date(a.started_at || 0).getTime()
      );

      setRuns(allRuns);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load runs');
    } finally {
      setLoading(false);
    }
  };

  const handleRunClick = (run: Run) => {
    // Toggle selection
    if (selectedRun?.id === run.id) {
      onSelectRun(null);
    } else {
      onSelectRun(run);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Runs</h2>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Runs</h2>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <XCircle className="w-12 h-12 text-red-500 mb-3" />
          <p className="text-sm text-gray-600">{error}</p>
          <button
            onClick={fetchRuns}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Runs</h2>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Play className="w-12 h-12 text-gray-400 mb-3" />
          <p className="text-sm text-gray-600">No agent runs found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-5 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Runs</h2>
        <p className="text-sm text-gray-500 mt-1">{runs.length} total</p>
      </div>
      
      <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
        {runs.map((run) => {
          const isSelected = selectedRun?.id === run.id;
          
          return (
            <button
              key={run.id}
              onClick={() => handleRunClick(run)}
              className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                isSelected ? 'bg-blue-50 border-l-4 border-blue-600' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  {/* Run ID */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      run.type === 'session' 
                        ? 'bg-purple-100 text-purple-700' 
                        : 'bg-blue-100 text-blue-700'
                    }`}>
                      {run.type}
                    </span>
                    <span className="text-sm font-mono text-gray-900 truncate">
                      {run.id.substring(0, 12)}
                    </span>
                  </div>

                  {/* Status and Mode */}
                  <div className="flex items-center gap-2 mb-2">
                    {run.status && (
                      <StatusBadge status={run.status} exitCode={run.exit_code} />
                    )}
                    {run.mode && (
                      <span className="text-xs text-gray-600">{run.mode}</span>
                    )}
                  </div>

                  {/* Times */}
                  <div className="text-xs text-gray-500 space-y-1">
                    <div className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      <span>Started: {formatTimestamp(run.started_at)}</span>
                    </div>
                    {run.ended_at && (
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>Ended: {formatTimestamp(run.ended_at)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StatusBadge({ status, exitCode }: { status: string; exitCode?: number }) {
  let icon;
  let colorClass;

  if (status === 'completed' || status === 'complete' || status === 'success') {
    icon = <CheckCircle2 className="w-3 h-3" />;
    colorClass = 'bg-green-100 text-green-700';
  } else if (status === 'failed' || status === 'error') {
    icon = <XCircle className="w-3 h-3" />;
    colorClass = 'bg-red-100 text-red-700';
  } else {
    icon = <Clock className="w-3 h-3" />;
    colorClass = 'bg-gray-100 text-gray-700';
  }

  return (
    <span className={`flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${colorClass}`}>
      {icon}
      {status}
      {exitCode !== undefined && ` (${exitCode})`}
    </span>
  );
}

function formatTimestamp(timestamp: string): string {
  if (!timestamp) {
    return '--';
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return '--';
  }
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}
