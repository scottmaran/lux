import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {CodexSession, CODEX_SESSION_SOURCE_REPLICA} from '../../../../packages/video-kit/src';

const PANEL_WIDTH = 900;
const PANEL_HEIGHT = 580;

export const CodexSessionComparison: React.FC = () => {
  const scale = Math.min(PANEL_WIDTH / CODEX_SESSION_SOURCE_REPLICA.width, PANEL_HEIGHT / CODEX_SESSION_SOURCE_REPLICA.height);

  return (
    <AbsoluteFill
      style={{
        background:
          'linear-gradient(145deg, #0f172a 0%, #111827 52%, #1f2937 100%)',
        fontFamily: 'ui-sans-serif, system-ui, sans-serif',
        color: '#E5E7EB',
        padding: 30,
      }}
    >
      <div style={{fontSize: 28, fontWeight: 700, marginBottom: 18}}>Codex Session Source vs Remotion Replica</div>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, height: '100%'}}>
        <div style={{display: 'flex', flexDirection: 'column', gap: 10}}>
          <div style={{fontSize: 18, fontWeight: 700}}>Source MP4</div>
          <div
            style={{
              width: PANEL_WIDTH,
              height: PANEL_HEIGHT,
              borderRadius: 14,
              overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.2)',
              boxShadow: '0 18px 34px rgba(0,0,0,0.35)',
            }}
          >
            <OffthreadVideo
              src={staticFile('codex_session_source.mp4')}
              style={{width: '100%', height: '100%', objectFit: 'cover'}}
            />
          </div>
        </div>

        <div style={{display: 'flex', flexDirection: 'column', gap: 10}}>
          <div style={{fontSize: 18, fontWeight: 700}}>Remotion Replica</div>
          <div
            style={{
              width: PANEL_WIDTH,
              height: PANEL_HEIGHT,
              borderRadius: 14,
              overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.2)',
              boxShadow: '0 18px 34px rgba(0,0,0,0.35)',
              position: 'relative',
              backgroundColor: '#111827',
            }}
          >
            <div
              style={{
                width: CODEX_SESSION_SOURCE_REPLICA.width,
                height: CODEX_SESSION_SOURCE_REPLICA.height,
                transform: `scale(${scale})`,
                transformOrigin: 'top left',
              }}
            >
              <CodexSession
                commandSteps={CODEX_SESSION_SOURCE_REPLICA.commandSteps}
                cardAtSec={CODEX_SESSION_SOURCE_REPLICA.cardAtSec}
                card={CODEX_SESSION_SOURCE_REPLICA.card}
                rows={CODEX_SESSION_SOURCE_REPLICA.rows}
                scroll={CODEX_SESSION_SOURCE_REPLICA.scroll}
                topBarTitle={CODEX_SESSION_SOURCE_REPLICA.topBarTitle}
                topBarTitleSteps={CODEX_SESSION_SOURCE_REPLICA.topBarTitleSteps}
                bottomRightLabel={CODEX_SESSION_SOURCE_REPLICA.bottomRightLabel}
                bottomRightAtSec={CODEX_SESSION_SOURCE_REPLICA.bottomRightAtSec}
                footerAtSec={CODEX_SESSION_SOURCE_REPLICA.footerAtSec}
                footerLines={CODEX_SESSION_SOURCE_REPLICA.footerLines}
              />
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
