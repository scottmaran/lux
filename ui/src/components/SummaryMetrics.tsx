import { useState, useEffect } from 'react';
import { Activity, FileEdit, Wifi } from 'lucide-react';
import type { Source, TimeRange, Run, TimelineEvent } from '../App';

interface SummaryMetricsProps {
  selectedSources: Source[];
  timeRange: TimeRange;
  selectedRun: Run | null;
}

export function SummaryMetrics({ selectedSources, timeRange, selectedRun }: SummaryMetricsProps) {
  const [metrics, setMetrics] = useState({
    processes: 0,
    fileChanges: 0,
    networkCalls: 0
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
  }, [selectedSources, timeRange, selectedRun]);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();

      if (selectedSources.length > 0) {
        params.append('source', selectedSources.join(','));
      } else {
        setMetrics({ processes: 0, fileChanges: 0, networkCalls: 0 });
        setLoading(false);
        return;
      }

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
      
      params.append('limit', '10000'); // High limit to get all events for counting

      const response = await fetch(`/api/timeline?${params}`);
      if (!response.ok) {
        throw new Error('Failed to fetch metrics');
      }
      const payload = await response.json();
      const events: TimelineEvent[] = Array.isArray(payload?.rows) ? payload.rows : [];

      // Compute metrics
      const processes = events.filter(e => e.event_type === 'exec').length;
      const fileChanges = events.filter(e => 
        e.event_type === 'fs_create' || 
        e.event_type === 'fs_unlink' || 
        e.event_type === 'fs_meta'
      ).length;
      const networkCalls = events.filter(e => e.event_type === 'net_summary').length;

      setMetrics({ processes, fileChanges, networkCalls });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const metricCards = [
    {
      label: 'Processes',
      value: metrics.processes,
      icon: Activity,
      color: 'blue'
    },
    {
      label: 'File Changes',
      value: metrics.fileChanges,
      icon: FileEdit,
      color: 'green'
    },
    {
      label: 'Network Calls',
      value: metrics.networkCalls,
      icon: Wifi,
      color: 'purple'
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {metricCards.map((metric) => {
        const Icon = metric.icon;
        const colorClasses = {
          blue: 'bg-blue-50 text-blue-600',
          green: 'bg-green-50 text-green-600',
          purple: 'bg-purple-50 text-purple-600'
        }[metric.color];

        return (
          <div key={metric.label} className="bg-white rounded-lg border border-gray-200 p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 mb-1">{metric.label}</p>
                <p className="text-2xl font-semibold text-gray-900">
                  {loading ? '—' : metric.value.toLocaleString()}
                </p>
              </div>
              <div className={`w-12 h-12 rounded-lg ${colorClasses} flex items-center justify-center`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
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
