import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Pause, Play, RotateCcw } from 'lucide-react';
import * as AsciinemaPlayer from 'asciinema-player';
import 'asciinema-player/dist/bundle/asciinema-player.css';
import type { Run, Source, TimelineEvent } from '../App';
import { TimelineEventRow } from './TimelineRow';

interface IncidentReplayProps {
  selectedRun: Run | null;
  selectedSources: Source[];
}

const SPEED_OPTIONS = [0.5, 1, 2, 4];
const TICK_MS = 120;

export function IncidentReplay({ selectedRun, selectedSources }: IncidentReplayProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [currentMs, setCurrentMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const startMsRef = useRef(0);
  const playerRef = useRef<any>(null);
  const [playerVersion, setPlayerVersion] = useState(0);
  const panelHeight = 320;
  const handlePlayerReady = useCallback((player: any | null) => {
    playerRef.current = player;
    setPlayerVersion((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (!selectedRun) {
      setEvents([]);
      setIsPlaying(false);
      setCurrentMs(0);
      setDurationMs(0);
      setError(null);
      playerRef.current = null;
      setPlayerVersion((prev) => prev + 1);
      return;
    }

    if (selectedSources.length === 0) {
      setEvents([]);
      setIsPlaying(false);
      setCurrentMs(0);
      setDurationMs(0);
      setError('Select at least one data source to replay.');
      return;
    }

    const fetchReplay = async () => {
      setLoading(true);
      setError(null);
      setIsPlaying(false);
      setCurrentMs(0);

      try {
        const params = new URLSearchParams();
        params.append('source', selectedSources.join(','));
        if (selectedRun.type === 'session') {
          params.append('session_id', selectedRun.id);
        } else {
          params.append('job_id', selectedRun.id);
        }
        if (selectedRun.started_at) {
          params.append('start', selectedRun.started_at);
        }
        if (selectedRun.ended_at) {
          params.append('end', selectedRun.ended_at);
        }

        const response = await fetch(`/api/timeline?${params}`);
        if (!response.ok) {
          throw new Error('Failed to fetch replay events');
        }
        const payload = await response.json();
        const rows: TimelineEvent[] = Array.isArray(payload?.rows) ? payload.rows : [];
        const sorted = rows.sort((a, b) =>
          new Date(a.ts).getTime() - new Date(b.ts).getTime()
        );
        setEvents(sorted);

        const firstTs = sorted[0]?.ts ?? selectedRun.started_at;
        const lastTs = sorted[sorted.length - 1]?.ts ?? selectedRun.ended_at ?? firstTs;
        const startMs = firstTs ? new Date(firstTs).getTime() : Date.now();
        const endMs = lastTs ? new Date(lastTs).getTime() : startMs;

        startMsRef.current = startMs;
        setDurationMs(Math.max(0, endMs - startMs));
      } catch (err) {
        setEvents([]);
        setDurationMs(0);
        setError(err instanceof Error ? err.message : 'Failed to load replay data');
      } finally {
        setLoading(false);
      }
    };

    fetchReplay();
  }, [selectedRun, selectedSources]);

  useEffect(() => {
    if (!isPlaying) {
      return;
    }

    if (playerRef.current) {
      const interval = window.setInterval(async () => {
        try {
          const seconds = await playerRef.current.getCurrentTime();
          if (typeof seconds === 'number') {
            const nextMs = Math.min(durationMs, Math.max(0, seconds * 1000));
            setCurrentMs(nextMs);
            if (durationMs > 0 && nextMs >= durationMs) {
              setIsPlaying(false);
            }
          }
        } catch {
          // ignore polling errors
        }
      }, TICK_MS);
      return () => window.clearInterval(interval);
    }

    const interval = window.setInterval(() => {
      setCurrentMs((prev) => {
        if (durationMs <= 0) {
          setIsPlaying(false);
          return 0;
        }
        const next = Math.min(durationMs, prev + TICK_MS * speed);
        if (next >= durationMs) {
          setIsPlaying(false);
        }
        return next;
      });
    }, TICK_MS);

    return () => window.clearInterval(interval);
  }, [isPlaying, speed, durationMs, playerVersion]);

  useEffect(() => {
    const player = playerRef.current;
    if (!player) {
      return;
    }

    player.getDuration().then((seconds: number) => {
      if (typeof seconds === 'number') {
        setDurationMs((prev) => Math.max(prev, seconds * 1000));
      }
    });

    const syncTime = async () => {
      const seconds = await player.getCurrentTime();
      if (typeof seconds === 'number') {
        setCurrentMs(Math.max(0, seconds * 1000));
      }
    };

    player.addEventListener('play', () => setIsPlaying(true));
    player.addEventListener('pause', () => setIsPlaying(false));
    player.addEventListener('ended', () => setIsPlaying(false));
    player.addEventListener('seeked', () => {
      syncTime().catch(() => undefined);
    });
  }, [playerVersion]);

  const visibleEvents = useMemo(() => {
    if (!events.length) {
      return [];
    }
    const cutoff = startMsRef.current + currentMs;
    const filtered = events.filter((event) => new Date(event.ts).getTime() <= cutoff);
    return filtered.slice(-200);
  }, [events, currentMs]);

  const visibleEventsSorted = useMemo(() => {
    if (!visibleEvents.length) {
      return [];
    }
    return [...visibleEvents].sort(
      (a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime()
    );
  }, [visibleEvents]);

  const playbackTime = formatPlaybackTime(currentMs);
  const playbackStamp = startMsRef.current
    ? new Date(startMsRef.current + currentMs).toLocaleString()
    : '--';

  const runLabel = selectedRun
    ? selectedRun.name?.trim() || `${selectedRun.type} ${selectedRun.id.substring(0, 8)}`
    : 'Select a run';

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="p-5 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Incident Replay</h2>
        <p className="text-sm text-gray-500 mt-1">{runLabel}</p>
      </div>

      {!selectedRun && (
        <div className="p-6 text-center text-sm text-gray-500">
          Select a run to replay its timeline and optional TUI recording.
        </div>
      )}

      {selectedRun && (
        <div className="p-6 space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => {
                const player = playerRef.current;
                if (player) {
                  if (isPlaying) {
                    player.pause();
                  } else {
                    player.play();
                  }
                } else {
                  setIsPlaying((prev) => !prev);
                }
              }}
              disabled={events.length === 0 || !!error}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-gray-300"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              {isPlaying ? 'Pause' : 'Play'}
            </button>
            <button
              type="button"
              onClick={() => {
                const player = playerRef.current;
                setIsPlaying(false);
                setCurrentMs(0);
                if (player) {
                  player.pause();
                  player.seek(0);
                }
              }}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md border border-gray-200 text-sm text-gray-700 hover:bg-gray-50"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>Speed</span>
              <select
                value={speed}
                onChange={(event) => setSpeed(Number(event.target.value))}
                className="border border-gray-300 rounded-md px-2 py-1 text-sm"
              >
                {SPEED_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}x
                  </option>
                ))}
              </select>
            </div>
            <div className="text-sm text-gray-500">
              {playbackTime} - {playbackStamp}
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <input
              type="range"
              min={0}
              max={Math.max(durationMs, 1)}
              step={250}
              value={currentMs}
              onChange={(event) => {
                const nextMs = Number(event.target.value);
                setCurrentMs(nextMs);
                const player = playerRef.current;
                if (player) {
                  player.seek(nextMs / 1000);
                }
              }}
              disabled={durationMs <= 0 || events.length === 0}
              className="w-full"
            />
            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>0:00</span>
              <span>{formatPlaybackTime(durationMs)}</span>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {loading && (
            <div className="text-sm text-gray-500">Loading replay events...</div>
          )}

          {!loading && !error && events.length === 0 && (
            <div className="text-sm text-gray-500">No events found for this run.</div>
          )}

          <div
            className="grid gap-6"
            style={{ gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)' }}
          >
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900">Replay Timeline</h3>
                <span className="text-xs text-gray-500">{visibleEvents.length} events shown</span>
              </div>
              <div
                className="divide-y divide-gray-200 overflow-y-auto"
                style={{ height: `${panelHeight}px` }}
              >
                {visibleEventsSorted.map((event, index) => (
                  <TimelineEventRow key={`${event.ts}:${event.event_type}:${index}`} event={event} />
                ))}
              </div>
            </div>

            <TuiReplay
              run={selectedRun}
              panelHeight={panelHeight}
              onPlayerReady={handlePlayerReady}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function TuiReplay({
  run,
  panelHeight,
  onPlayerReady
}: {
  run: Run;
  panelHeight: number;
  onPlayerReady: (player: any | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<any>(null);

  const hasCast = run.type === 'session' && (run.tui_available ?? Boolean(run.tui_cast_path));
  const castUrl = hasCast ? `/api/sessions/${run.id}/tui.cast` : null;

  useEffect(() => {
    if (!castUrl || !containerRef.current) {
      onPlayerReady(null);
      return;
    }

    containerRef.current.innerHTML = '';
    const player = AsciinemaPlayer.create(castUrl, containerRef.current, {
      autoPlay: false,
      preload: true,
      fit: 'both'
    });
    playerRef.current = player;
    onPlayerReady(player);

    return () => {
      if (playerRef.current?.dispose) {
        playerRef.current.dispose();
      }
      onPlayerReady(null);
      playerRef.current = null;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [castUrl, onPlayerReady]);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">TUI Replay</h3>
        {hasCast ? (
          <span className="text-xs text-emerald-600">asciinema v2</span>
        ) : (
          <span className="text-xs text-gray-400">not available</span>
        )}
      </div>
      <div
        className="bg-gray-900 text-gray-100 flex items-center justify-center"
        style={{ height: `${panelHeight}px` }}
      >
        {castUrl ? (
          <div
            className="bg-gray-900"
            style={{
              width: '100%',
              height: `${panelHeight}px`,
              maxWidth: '100%',
              resize: 'both',
              overflow: 'hidden',
              minWidth: '240px',
              minHeight: '200px'
            }}
          >
            <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
          </div>
        ) : (
          <div className="text-sm text-gray-400">
            No TUI recording for this run.
          </div>
        )}
      </div>
    </div>
  );
}

function formatPlaybackTime(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) {
    return '0:00';
  }
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
