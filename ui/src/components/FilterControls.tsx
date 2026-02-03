import { Clock } from 'lucide-react';
import type { Source, TimeRange } from '../App';

interface FilterControlsProps {
  selectedSources: Source[];
  onSourcesChange: (sources: Source[]) => void;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
}

export function FilterControls({
  selectedSources,
  onSourcesChange,
  timeRange,
  onTimeRangeChange
}: FilterControlsProps) {
  const toggleSource = (source: Source) => {
    if (selectedSources.includes(source)) {
      onSourcesChange(selectedSources.filter(s => s !== source));
    } else {
      onSourcesChange([...selectedSources, source]);
    }
  };

  const timeRanges: { value: TimeRange; label: string }[] = [
    { value: '15m', label: '15 min' },
    { value: '1h', label: '1 hour' },
    { value: '24h', label: '24 hours' },
    { value: '7d', label: '7 days' }
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Source Toggles */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block">
            Data Source
          </label>
          <div className="flex gap-2">
            <button
              onClick={() => toggleSource('audit')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                selectedSources.includes('audit')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Commands
            </button>
            <button
              onClick={() => toggleSource('ebpf')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                selectedSources.includes('ebpf')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Network
            </button>
            <button
              onClick={() => toggleSource('proxy')}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                selectedSources.includes('proxy')
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              HTTP Proxy
            </button>
          </div>
        </div>

        {/* Time Range Presets */}
        <div>
          <label className="text-sm font-medium text-gray-700 mb-2 block flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Time Range
          </label>
          <div className="flex gap-2">
            {timeRanges.map((range) => (
              <button
                key={range.value}
                onClick={() => onTimeRangeChange(range.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  timeRange === range.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {selectedSources.length === 0 && (
        <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
          <p className="text-sm text-amber-800">
            ⚠️ No data sources selected. Select at least one source to view events.
          </p>
        </div>
      )}
    </div>
  );
}
