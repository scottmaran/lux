import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {DEFAULT_CODEX_SESSION_THEME, type CodexSessionTheme} from './theme';
import type {
  CodexSessionCardConfig,
  CodexSessionCommandStep,
  CodexSessionPartTone,
  CodexSessionProps,
  CodexSessionRow,
  CodexSessionRowPart,
} from './types';

const defaultCard: CodexSessionCardConfig = {
  title: 'OpenAI Codex',
  version: 'v0.104.0',
  modelLabel: 'model:',
  modelValue: 'gpt-5.3-codex xhigh',
  modelAction: '/model to change',
  directoryLabel: 'directory:',
  directoryValue: '/work',
  tipLabel: 'Tip: New 2x rate limits until April 2nd.',
};

const blockCursor = '|';

const partToneStyle = (tone: CodexSessionPartTone, theme: CodexSessionTheme): React.CSSProperties => {
  switch (tone) {
    case 'muted':
      return {color: theme.mutedText};
    case 'accent':
      return {color: theme.accentText};
    default:
      return {color: theme.bodyText};
  }
};

const rowKey = (row: CodexSessionRow, index: number): string => {
  const text = row.parts?.map((part) => part.text).join('') ?? row.kind ?? '';
  return `${row.atSec}-${index}-${text}`;
};

const renderRowParts = (parts: CodexSessionRowPart[], theme: CodexSessionTheme): React.ReactNode => {
  return parts.map((part, index) => {
    const tone = part.tone ?? 'normal';
    return (
      <span
        key={`${part.text}-${index}`}
        style={{
          ...partToneStyle(tone, theme),
          fontWeight: part.bold ? 700 : 500,
          fontStyle: part.italic ? 'italic' : 'normal',
          whiteSpace: 'pre-wrap',
        }}
      >
        {part.text}
      </span>
    );
  });
};

const typedCommandAtTime = (step: CodexSessionCommandStep, currentSec: number, fps: number): string => {
  if (!step.command) {
    return '';
  }

  const typingDurationSec = step.typingDurationSec ?? 1;
  const elapsedSec = currentSec - step.atSec;
  if (elapsedSec <= 0) {
    return '';
  }

  const elapsedFrames = Math.floor(elapsedSec * fps);
  const totalFrames = Math.max(1, Math.floor(typingDurationSec * fps));
  const progress = Math.min(1, elapsedFrames / totalFrames);
  const visibleChars = Math.floor(step.command.length * progress);
  return step.command.slice(0, visibleChars);
};

const glyphForRow = (row: CodexSessionRow): string => {
  switch (row.glyph ?? 'none') {
    case 'dot':
      return '*';
    case 'hollow':
      return 'o';
    case 'arrow':
      return '>';
    default:
      return '';
  }
};

const scrollOffsetAt = (
  sec: number,
  keyframes: {atSec: number; offset: number}[] | undefined,
): number => {
  if (!keyframes || keyframes.length === 0) {
    return 0;
  }

  if (sec <= keyframes[0].atSec) {
    return keyframes[0].offset;
  }

  for (let i = 0; i < keyframes.length - 1; i += 1) {
    const a = keyframes[i];
    const b = keyframes[i + 1];
    if (sec <= b.atSec) {
      return interpolate(sec, [a.atSec, b.atSec], [a.offset, b.offset], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
    }
  }

  return keyframes[keyframes.length - 1].offset;
};

const actionParts = (text: string): {lead: string; tail: string} => {
  const split = text.indexOf(' ');
  if (split === -1) {
    return {lead: text, tail: ''};
  }

  return {
    lead: text.slice(0, split),
    tail: text.slice(split),
  };
};

export const CodexSession: React.FC<CodexSessionProps> = ({
  commandSteps,
  cardAtSec,
  card,
  rows,
  scroll,
  backgroundColor,
  topBarTitle = 'lux_workspace - docker-compose < lux shim exec codex --- 82x24',
  bottomRightLabel = '100% context left',
  theme,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentSec = frame / fps;
  const activeRows = rows.filter((row) => row.atSec <= currentSec);
  const cardConfig = card ?? defaultCard;
  const contentScroll = scrollOffsetAt(currentSec, scroll);
  const palette = {...DEFAULT_CODEX_SESSION_THEME, ...theme};
  const cardAction = cardConfig.modelAction ? actionParts(cardConfig.modelAction) : null;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: backgroundColor ?? palette.pageBg,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      }}
    >
      <div
        style={{
          height: 44,
          borderBottom: `1px solid ${palette.topBarBorder}`,
          backgroundColor: palette.topBarBg,
          display: 'flex',
          alignItems: 'center',
          padding: '0 12px',
          gap: 8,
          color: palette.topBarText,
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        <span style={{width: 12, height: 12, borderRadius: 999, backgroundColor: palette.dotRed}} />
        <span style={{width: 12, height: 12, borderRadius: 999, backgroundColor: palette.dotYellow}} />
        <span style={{width: 12, height: 12, borderRadius: 999, backgroundColor: palette.dotGreen}} />
        <span style={{marginLeft: 10}}>{topBarTitle}</span>
      </div>

      <div
        style={{
          position: 'absolute',
          inset: '44px 0 0 0',
          overflow: 'hidden',
          padding: '16px 12px 14px 12px',
          color: palette.bodyText,
        }}
      >
        <div
          style={{
            transform: `translateY(${-contentScroll}px)`,
            fontSize: 18,
            lineHeight: 1.28,
          }}
        >
          {commandSteps
            .filter((step) => step.atSec <= currentSec)
            .map((step, index, visibleSteps) => {
              const typedText = typedCommandAtTime(step, currentSec, fps);
              const isLastVisible = index === visibleSteps.length - 1;
              const showCursor = isLastVisible;
              const fullCommand = step.command ?? '';
              const displayCommand = isLastVisible ? typedText : fullCommand;

              if (step.bracketed) {
                return (
                  <div key={`${step.atSec}-${index}`} style={{marginBottom: 10}}>
                    <span style={{fontWeight: 500}}>[{step.prompt}% </span>
                    <span style={{fontWeight: 500}}>{displayCommand}</span>
                    {showCursor ? <span style={{color: palette.cursor, fontWeight: 700}}>{blockCursor}</span> : null}
                    <span style={{fontWeight: 500}}>]</span>
                  </div>
                );
              }

              return (
                <div key={`${step.atSec}-${index}`} style={{marginBottom: 10}}>
                  <span style={{fontWeight: 500}}>{step.prompt}% </span>
                  <span style={{fontWeight: 500}}>{displayCommand}</span>
                  {showCursor ? <span style={{color: palette.cursor, fontWeight: 700}}>{blockCursor}</span> : null}
                </div>
              );
            })}

          {currentSec >= cardAtSec ? (
            <>
              <div
                style={{
                  border: `1px solid ${palette.cardBorder}`,
                  borderRadius: 8,
                  backgroundColor: palette.cardBg,
                  padding: '14px 16px',
                  width: 582,
                  marginBottom: 18,
                }}
              >
                <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10}}>
                  <span style={{color: palette.mutedText}}>{'>_'}</span>
                  <span style={{fontWeight: 700}}>{cardConfig.title}</span>
                  <span style={{color: palette.mutedText}}>{`(${cardConfig.version})`}</span>
                </div>
                <div style={{display: 'grid', gridTemplateColumns: '115px 1fr', rowGap: 0}}>
                  <span style={{color: palette.mutedText}}>{cardConfig.modelLabel}</span>
                  <span>
                    <span>{cardConfig.modelValue}</span>
                    {cardAction ? <span style={{color: palette.mutedText}}>{'   '}</span> : null}
                    {cardAction ? <span style={{color: palette.accentText}}>{cardAction.lead}</span> : null}
                    {cardAction ? <span style={{color: palette.mutedText}}>{cardAction.tail}</span> : null}
                  </span>
                  <span style={{color: palette.mutedText}}>{cardConfig.directoryLabel}</span>
                  <span>{cardConfig.directoryValue}</span>
                </div>
              </div>

              {cardConfig.tipLabel ? (
                <div style={{marginBottom: 20}}>
                  <span style={{fontWeight: 700}}>Tip: </span>
                  <span style={{fontStyle: 'italic'}}>{cardConfig.tipLabel.replace('Tip: ', '')}</span>
                </div>
              ) : null}
            </>
          ) : null}

          {activeRows.map((row, index) => {
            if (row.kind === 'spacer') {
              return <div key={rowKey(row, index)} style={{height: 16}} />;
            }

            if (row.kind === 'separator') {
              return (
                <div
                  key={rowKey(row, index)}
                  style={{
                    borderTop: `2px solid ${palette.separator}`,
                    margin: '12px 0 12px 0',
                  }}
                />
              );
            }

            const glyph = glyphForRow(row);
            return (
              <div
                key={rowKey(row, index)}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  marginBottom: 8,
                  marginLeft: row.indent ?? 0,
                  ...row.style,
                }}
              >
                <span style={{width: 20, color: palette.mutedText}}>{glyph}</span>
                <span>{row.parts ? renderRowParts(row.parts, palette) : null}</span>
              </div>
            );
          })}

          <div style={{height: 20}} />
          <div style={{display: 'flex', gap: 10, color: palette.mutedText, marginBottom: 8}}>
            <span style={{width: 20}}>{'>'}</span>
            <span>Improve documentation in @filename</span>
          </div>
          <div style={{display: 'flex', gap: 10, color: palette.mutedText}}>
            <span style={{width: 20}}>{'?'}</span>
            <span>for shortcuts</span>
          </div>
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          right: 12,
          bottom: 8,
          color: palette.mutedText,
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {bottomRightLabel}
      </div>
    </AbsoluteFill>
  );
};
