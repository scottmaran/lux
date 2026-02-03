import type { TimelineEvent } from '../App';
import { formatTimestamp, getEventTarget, getEventTypeColor, getExecStatus } from './timelineUtils';

export function TimelineEventRow({ event }: { event: TimelineEvent }) {
  const target = getEventTarget(event);
  const execStatus = getExecStatus(event);
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
          {execStatus && (
            <span className={`flex items-center gap-1 font-medium px-2 py-0.5 rounded ${execStatus.className}`}>
              {execStatus.label}
            </span>
          )}
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
