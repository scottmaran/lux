import { useState, useEffect, useRef } from 'react';
import { Activity, AlertCircle } from 'lucide-react';
import type { Source, TimeRange, Run, TimelineEvent } from '../App';

interface TimelineProps {
  selectedSources: Source[];
  timeRange: TimeRange;
  selectedRun: Run | null;
}

const POLL_INTERVAL = 2000; // 2 seconds

export function Timeline({ selectedSources, timeRange, selectedRun }: TimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    fetchEvents();

    // Set up polling when tab is active
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
  }, [selectedSources, timeRange, selectedRun]);

  const startPolling = () => {
    stopPolling(); // Clear any existing interval
    pollIntervalRef.current = window.setInterval(() => {
      fetchEvents(true); // Silent refresh
    }, POLL_INTERVAL);
  };

  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const fetchEvents = async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }
    setError(null);

    try {
      // Don't fetch if no sources selected
      if (selectedSources.length === 0) {
        setEvents([]);
        setLoading(false);
        return;
      }

      const params = new URLSearchParams();
      params.append('source', selectedSources.join(','));
      
      const { start, end } = getTimeRangeParams(timeRange);
      params.append('start', start);
      params.append('end', end);
      
      if (selectedRun) {
        if (selectedRun.type === 'session') {
          params.append('session_id', selectedRun.id);
        } else {
          params.append('job_id', selectedRun.id);
        }
      }
      
      params.append('limit', '500'); // Reasonable limit for UI

      const response = await fetch(`/api/timeline?${params}`);

      if (!response.ok) {
        throw new Error('Failed to fetch timeline events');
      }

      const payload = await response.json();
      const rows: TimelineEvent[] = Array.isArray(payload?.rows) ? payload.rows : [];

      // Sort by timestamp descending (latest first)
      const sorted = rows.sort((a, b) =>
        new Date(b.ts).getTime() - new Date(a.ts).getTime()
      );

      setEvents(sorted);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load events');
    } finally {
      setLoading(false);
    }
  };

  if (loading && events.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mb-3" />
          <p className="text-sm text-gray-600">{error}</p>
          <button
            onClick={() => fetchEvents()}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (selectedSources.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Activity className="w-12 h-12 text-gray-400 mb-3" />
          <p className="text-sm text-gray-600">Select a data source to view events</p>
        </div>
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Timeline</h2>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Activity className="w-12 h-12 text-gray-400 mb-3" />
          <p className="text-sm text-gray-600">No events found</p>
          <p className="text-xs text-gray-500 mt-1">
            {selectedRun 
              ? 'Try selecting a different run or adjusting filters'
              : 'Try adjusting the time range or filters'
            }
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-5 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Timeline</h2>
          <p className="text-sm text-gray-500 mt-1">
            {events.length} event{events.length !== 1 ? 's' : ''}
            {selectedRun &&
              ` • Filtered by ${selectedRun.name?.trim() || `${selectedRun.type} ${selectedRun.id.substring(0, 8)}`}`}
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          Auto-refresh active
        </div>
      </div>

      <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
        {events.map((event, index) => (
          <TimelineEventRow key={getEventKey(event, index)} event={event} />
        ))}
      </div>
    </div>
  );
}

function TimelineEventRow({ event }: { event: TimelineEvent }) {
  const target = getEventTarget(event);
  const sourceColor = event.source === 'audit' 
    ? 'bg-indigo-100 text-indigo-700' 
    : 'bg-emerald-100 text-emerald-700';

  return (
    <div className="p-4 hover:bg-gray-50 transition-colors">
      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono whitespace-nowrap">
            {formatTimestamp(event.ts)}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${sourceColor}`}>
            {event.source}
          </span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded ${getEventTypeColor(event.event_type)}`}>
            {event.event_type}
          </span>
        </div>
      </div>

      <div className="ml-0">
        <p className="text-sm text-gray-900 font-medium mb-1 break-all">
          {target}
        </p>
        <div className="flex items-center gap-3 text-xs text-gray-600">
          {event.comm && (
            <span className="flex items-center gap-1">
              <span className="text-gray-400">Process:</span>
              <span className="font-mono">{event.comm}</span>
            </span>
          )}
          {event.pid !== undefined && (
            <span className="flex items-center gap-1">
              <span className="text-gray-400">PID:</span>
              <span className="font-mono">{event.pid}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function getEventTarget(event: TimelineEvent): string {
  const { event_type } = event;
  const details = event.details || {};

  switch (event_type) {
    case 'exec':
      return details.cmd || details.cwd || 'Unknown command';
    
    case 'fs_create':
    case 'fs_unlink':
    case 'fs_meta':
      return details.path || details.cmd || 'Unknown path';
    
    case 'net_summary': {
      const parts: string[] = [];
      if (details.dns_names && Array.isArray(details.dns_names) && details.dns_names.length > 0) {
        parts.push(details.dns_names.join(', '));
      }
      if (details.dst_ip && details.dst_port) {
        parts.push(`${details.dst_ip}:${details.dst_port}`);
      } else if (details.dst_ip) {
        parts.push(details.dst_ip);
      }
      return parts.length > 0 ? parts.join(' → ') : 'Network connection';
    }
    
    case 'unix_connect':
      return details.unix?.path || details.path || 'Unix socket connection';
    
    case 'dns_query':
    case 'dns_response':
      return `${details.dns?.query_name || 'DNS'} (${details.dns?.query_type || 'unknown'})`;
    
    default:
      return JSON.stringify(details);
  }
}

function getEventTypeColor(eventType: string): string {
  if (eventType === 'exec') {
    return 'bg-blue-100 text-blue-700';
  }
  if (eventType.startsWith('fs_')) {
    return 'bg-green-100 text-green-700';
  }
  if (eventType.startsWith('net_') || eventType.startsWith('dns_')) {
    return 'bg-purple-100 text-purple-700';
  }
  if (eventType.startsWith('unix_')) {
    return 'bg-orange-100 text-orange-700';
  }
  return 'bg-gray-100 text-gray-700';
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
    minute: '2-digit',
    second: '2-digit'
  });
}

function getEventKey(event: TimelineEvent, index: number): string {
  const parts = [
    event.ts,
    event.source,
    event.event_type,
    event.pid ?? 'na',
    index
  ];
  return parts.join(':');
}

function getTimeRangeParams(range: TimeRange): { start: string; end: string } {
  const end = new Date();
  const start = new Date();

  switch (range) {
    case '15m':
      start.setMinutes(start.getMinutes() - 15);
      break;
    case '1h':
      start.setHours(start.getHours() - 1);
      break;
    case '24h':
      start.setHours(start.getHours() - 24);
      break;
    case '7d':
      start.setDate(start.getDate() - 7);
      break;
  }

  return {
    start: start.toISOString(),
    end: end.toISOString()
  };
}
