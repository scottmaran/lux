import { useState, useEffect, useRef, useCallback, type MouseEvent } from 'react';
import { Play, CheckCircle2, XCircle, Clock, Pencil, Loader2 } from 'lucide-react';
import type { Run } from '../App';

interface RunsListProps {
  selectedRun: Run | null;
  onSelectRun: (run: Run | null) => void;
}

const POLL_INTERVAL = 2000; // 2 seconds

export function RunsList({ selectedRun, onSelectRun }: RunsListProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingRunId, setEditingRunId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const [savingRunId, setSavingRunId] = useState<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);
  const editingRunIdRef = useRef<string | null>(null);

  useEffect(() => {
    editingRunIdRef.current = editingRunId;
  }, [editingRunId]);

  const fetchRuns = useCallback(async (silent = false) => {
    if (editingRunIdRef.current) {
      return;
    }
    if (!silent) {
      setLoading(true);
    }
    if (!silent) {
      setError(null);
    }
    try {
      // Fetch sessions and jobs in parallel
      const [sessionsRes, jobsRes] = await Promise.all([
        fetch('/api/sessions', { cache: 'no-store' }),
        fetch('/api/jobs', { cache: 'no-store' })
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
          name: s.name,
          mode: s.mode,
          exit_code: s.exit_code,
          started_at: s.started_at,
          ended_at: s.ended_at
        })),
        ...jobs.map((j: any) => ({
          id: j.job_id,
          type: 'job' as const,
          name: j.name,
          status: j.status,
          exit_code: j.exit_code,
          started_at: j.started_at || j.submitted_at,
          ended_at: j.ended_at
        }))
      ].sort((a, b) =>
        new Date(b.started_at || 0).getTime() - new Date(a.started_at || 0).getTime()
      );

      setRuns(allRuns);
      setError(null);
    } catch (err) {
      if (!silent) {
        setError(err instanceof Error ? err.message : 'Failed to load runs');
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchRuns();

    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        startPolling();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    if (!document.hidden) {
      startPolling();
    }

    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchRuns]);

  const startPolling = () => {
    stopPolling();
    pollIntervalRef.current = window.setInterval(() => {
      fetchRuns(true);
    }, POLL_INTERVAL);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };


  const handleRunClick = (run: Run) => {
    if (editingRunId) {
      return;
    }
    // Toggle selection
    if (selectedRun?.id === run.id) {
      onSelectRun(null);
    } else {
      onSelectRun(run);
    }
  };

  const startEdit = (run: Run, event: MouseEvent) => {
    event.stopPropagation();
    setEditingRunId(run.id);
    setEditValue(run.name ?? '');
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingRunId(null);
    setEditValue('');
    setEditError(null);
  };

  const saveEdit = async (run: Run) => {
    const trimmed = editValue.trim();
    if (!trimmed) {
      setEditError('Name is required');
      return;
    }
    const current = (run.name ?? '').trim();
    if (trimmed === current) {
      cancelEdit();
      return;
    }
    setSavingRunId(run.id);
    setEditError(null);
    try {
      const endpoint = run.type === 'session' ? `/api/sessions/${run.id}` : `/api/jobs/${run.id}`;
      const response = await fetch(endpoint, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const message = payload?.error || 'Failed to rename run';
        throw new Error(message);
      }
      setRuns((prev) =>
        prev.map((item) =>
          item.id === run.id && item.type === run.type ? { ...item, name: trimmed } : item
        )
      );
      cancelEdit();
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Failed to rename run');
    } finally {
      setSavingRunId(null);
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
          const isEditing = editingRunId === run.id;
          const displayName = (run.name || '').trim();

          return (
            <div
              key={run.id}
              onClick={() => handleRunClick(run)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  handleRunClick(run);
                }
              }}
              role="button"
              tabIndex={0}
              className={`w-full text-left p-4 hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                isSelected ? 'bg-blue-50 border-l-4 border-blue-600' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  {/* Run Name + Type */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      run.type === 'session' 
                        ? 'bg-purple-100 text-purple-700' 
                        : 'bg-blue-100 text-blue-700'
                    }`}>
                      {run.type}
                    </span>
                    {isEditing ? (
                      <div className="flex-1 min-w-0">
                        <input
                          value={editValue}
                          onChange={(event) => setEditValue(event.target.value)}
                          onClick={(event) => event.stopPropagation()}
                          onBlur={() => saveEdit(run)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault();
                              saveEdit(run);
                            } else if (event.key === 'Escape') {
                              event.preventDefault();
                              cancelEdit();
                            }
                          }}
                          className="w-full text-sm text-gray-900 border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="Add name"
                          disabled={savingRunId === run.id}
                        />
                        {editError && (
                          <div className="text-xs text-red-600 mt-1">{editError}</div>
                        )}
                      </div>
                    ) : (
                      <span className={`text-sm truncate ${displayName ? 'text-gray-900 font-medium' : 'text-gray-500 italic'}`}>
                        {displayName || 'Add name'}
                      </span>
                    )}
                    {!isEditing && (
                      <button
                        type="button"
                        onClick={(event) => startEdit(run, event)}
                        className="ml-auto inline-flex items-center justify-center w-7 h-7 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                        aria-label="Rename run"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                    )}
                    {isEditing && savingRunId === run.id && (
                      <span className="ml-auto text-xs text-gray-400 flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Saving
                      </span>
                    )}
                  </div>

                  {/* Run ID */}
                  <div className="text-xs font-mono text-gray-500 truncate mb-2">
                    {run.id.substring(0, 12)}
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
            </div>
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
