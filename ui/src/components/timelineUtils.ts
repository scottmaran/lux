import type { TimelineEvent } from '../App';

export function getEventTarget(event: TimelineEvent): string {
  const { event_type } = event;
  const details = event.details || {};

  switch (event_type) {
    case 'exec':
      if (details.exec_success === false && details.exec_attempted_path) {
        return details.exec_attempted_path;
      }
      return details.cmd || details.exec_attempted_path || details.cwd || 'Unknown command';

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
      return parts.length > 0 ? parts.join(' -> ') : 'Network connection';
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

export function getEventTypeColor(eventType: string): string {
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

export function getExecStatus(event: TimelineEvent): { label: string; className: string } | null {
  if (event.event_type !== 'exec') {
    return null;
  }
  const details = event.details || {};
  if (details.exec_success === undefined) {
    return null;
  }
  const success = Boolean(details.exec_success);
  if (success) {
    return { label: 'exec ok', className: 'bg-emerald-100 text-emerald-700' };
  }
  let label = 'exec failed';
  if (details.exec_errno_name) {
    label = `exec failed (${details.exec_errno_name})`;
  } else if (typeof details.exec_exit === 'number') {
    label = `exec failed (exit=${details.exec_exit})`;
  }
  return { label, className: 'bg-red-100 text-red-700' };
}

export function formatTimestamp(timestamp: string): string {
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
