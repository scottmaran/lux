import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { ArrowLeftRight } from 'lucide-react';
import { Timeline } from './components/Timeline';
import { RunsList } from './components/RunsList';
import { SummaryMetrics } from './components/SummaryMetrics';
import { FilterControls } from './components/FilterControls';
import { IncidentReplay } from './components/IncidentReplay';

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
  name?: string;
  mode?: string;
  status?: string;
  exit_code?: number;
  started_at?: string;
  ended_at?: string;
  tui_cast_path?: string;
  tui_cast_format?: string;
  tui_available?: boolean;
}

function App() {
  const [selectedSources, setSelectedSources] = useState<Source[]>(['audit', 'ebpf']);
  const [timeRange, setTimeRange] = useState<TimeRange>('1h');
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [splitPercent, setSplitPercent] = useState(66);
  const [isWide, setIsWide] = useState(false);
  const splitRef = useRef<HTMLDivElement | null>(null);
  const draggingRef = useRef(false);
  const wideBreakpoint = 640;

  useEffect(() => {
    const saved = window.localStorage.getItem('ui.panelSplitPercent');
    if (saved) {
      const parsed = Number.parseFloat(saved);
      if (!Number.isNaN(parsed)) {
        setSplitPercent(Math.min(80, Math.max(20, parsed)));
      }
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem('ui.panelSplitPercent', splitPercent.toFixed(2));
  }, [splitPercent]);

  useEffect(() => {
    const node = splitRef.current;
    if (!node) {
      return;
    }
    const update = () => {
      const width = node.getBoundingClientRect().width;
      setIsWide(width >= wideBreakpoint);
    };
    update();
    if (typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(update);
      observer.observe(node);
      return () => observer.disconnect();
    }
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [wideBreakpoint]);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      if (!draggingRef.current || !splitRef.current) {
        return;
      }
      const rect = splitRef.current.getBoundingClientRect();
      const minLeft = 320;
      const minRight = 280;
      if (rect.width <= minLeft + minRight) {
        setSplitPercent(50);
        return;
      }
      const raw = event.clientX - rect.left;
      const clamped = Math.min(rect.width - minRight, Math.max(minLeft, raw));
      const next = (clamped / rect.width) * 100;
      setSplitPercent(next);
    };

    const handlePointerUp = () => {
      if (!draggingRef.current) {
        return;
      }
      draggingRef.current = false;
      document.body.style.cursor = '';
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, []);

  const startDrag = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (!isWide) {
      return;
    }
    draggingRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.style.cursor = 'col-resize';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="px-6 py-4">
          <h1 className="text-xl font-semibold text-gray-900">Lasso</h1>
          <p className="text-sm text-gray-500 mt-1">Verifiability & Auditability for your AI agents</p>
          <p className="text-sm text-gray-500 mt-1">A dedicated harness for OS-level tracking of everything your agents do</p>
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

        {/* Incident Replay */}
        <IncidentReplay
          selectedRun={selectedRun}
          selectedSources={selectedSources}
        />

        {/* Split Content: Timeline + Runs */}
        <div
          ref={splitRef}
          className={`flex ${isWide ? 'flex-row' : 'flex-col gap-6'}`}
        >
          <div
            className={isWide ? 'pr-3' : ''}
            style={
              isWide
                ? { flexBasis: `${splitPercent}%`, flexGrow: 0, flexShrink: 0 }
                : undefined
            }
          >
            <Timeline
              selectedSources={selectedSources}
              timeRange={timeRange}
              selectedRun={selectedRun}
            />
          </div>

          <div className={isWide ? 'flex items-stretch' : 'hidden'}>
            <button
              type="button"
              aria-label="Resize panels"
              onPointerDown={startDrag}
              className="group flex items-stretch focus:outline-none"
              style={{ touchAction: 'none' }}
            >
              <div className="w-6 cursor-col-resize flex items-center justify-center">
                <div className="h-10 w-5 rounded-full border border-gray-200 bg-gray-50 text-gray-400 flex items-center justify-center transition-colors group-hover:bg-gray-100 group-hover:text-gray-600">
                  <ArrowLeftRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </button>
          </div>

          <div
            className={isWide ? 'pl-3' : ''}
            style={
              isWide
                ? { flexBasis: `${100 - splitPercent}%`, flexGrow: 0, flexShrink: 0 }
                : undefined
            }
          >
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
