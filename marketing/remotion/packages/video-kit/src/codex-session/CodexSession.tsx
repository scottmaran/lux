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

const defaultFooterLines = [
  {glyph: '>', text: 'Improve documentation in @filename'},
  {glyph: '?', text: 'for shortcuts'},
];

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

const renderAnimatedScanBold = (
  text: string,
  frame: number,
  fps: number,
  rowAtSec: number,
  baseWeight: number,
): React.ReactNode => {
  if (!text) {
    return text;
  }

  const glyphCount = Math.max(1, text.length);
  const rowStartFrame = Math.floor(rowAtSec * fps);
  const elapsedFrames = Math.max(0, frame - rowStartFrame);
  const stepFrames = Math.max(1, Math.round(fps * 0.05));
  const activeIndex = Math.floor(elapsedFrames / stepFrames) % glyphCount;
  const boldWidthChars = Math.min(3, glyphCount);

  return (
    <span style={{position: 'relative', display: 'inline-block', whiteSpace: 'pre'}}>
      <span style={{fontWeight: baseWeight}}>{text}</span>
      <span
        style={{
          position: 'absolute',
          left: `${activeIndex}ch`,
          top: 0,
          width: `${boldWidthChars}ch`,
          overflow: 'hidden',
          whiteSpace: 'pre',
          fontWeight: 760,
        }}
      >
        <span style={{display: 'inline-block', transform: `translateX(-${activeIndex}ch)`}}>
          {text}
        </span>
      </span>
    </span>
  );
};

const renderRowParts = ({
  parts,
  theme,
  frame,
  fps,
  rowAtSec,
  rowAnimation,
}: {
  parts: CodexSessionRowPart[];
  theme: CodexSessionTheme;
  frame: number;
  fps: number;
  rowAtSec: number;
  rowAnimation?: 'none' | 'scan-bold';
}): React.ReactNode => {
  return parts.map((part, index) => {
    const tone = part.tone ?? 'normal';
    const animation = part.animation ?? rowAnimation ?? 'none';
    const staticWeight = part.bold ? 700 : 500;
    const animatedBaseWeight = 460;

    return (
      <span
        key={`${part.text}-${index}`}
        style={{
          ...partToneStyle(tone, theme),
          fontWeight: animation === 'scan-bold' ? animatedBaseWeight : staticWeight,
          fontStyle: part.italic ? 'italic' : 'normal',
          whiteSpace: 'pre-wrap',
        }}
      >
        {animation === 'scan-bold'
          ? renderAnimatedScanBold(part.text, frame, fps, rowAtSec, animatedBaseWeight)
          : part.text}
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

const rowPushOffsetAt = (
  sec: number,
  fps: number,
  pushes: {atSec: number; offset: number; durationFrames?: number}[] | undefined,
): number => {
  if (!pushes || pushes.length === 0) {
    return 0;
  }

  return pushes.reduce((acc, push) => {
    const elapsedFrames = Math.max(0, (sec - push.atSec) * fps);
    if (elapsedFrames <= 0) {
      return acc;
    }

    const durationFrames = push.durationFrames ?? Math.max(1, Math.round(fps * 0.14));
    const progress = Math.min(1, elapsedFrames / durationFrames);
    const easedProgress = 1 - (1 - progress) * (1 - progress);
    return acc + push.offset * easedProgress;
  }, 0);
};

const blinkCursorVisibleAt = (frame: number, fps: number): boolean => {
  const blinkFrames = Math.max(1, Math.round(fps * 0.5));
  return Math.floor(frame / blinkFrames) % 2 === 0;
};

const topBarTitleAtTime = (
  sec: number,
  fallbackTitle: string,
  titleSteps: {atSec: number; title: string}[] | undefined,
): string => {
  if (!titleSteps || titleSteps.length === 0) {
    return fallbackTitle;
  }

  let activeTitle = fallbackTitle;
  for (const step of titleSteps) {
    if (step.atSec > sec) {
      break;
    }

    activeTitle = step.title;
  }

  return activeTitle;
};

export const CodexSession: React.FC<CodexSessionProps> = ({
  commandSteps,
  cardAtSec,
  card,
  rows,
  scroll,
  rowPushes,
  backgroundColor,
  topBarTitle = 'lux_workspace --zsh -- 82x24',
  topBarTitleSteps,
  bottomRightLabel = '100% context left',
  bottomRightAtSec = 0,
  footerAtSec = 0,
  footerLines = defaultFooterLines,
  theme,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const currentSec = frame / fps;
  const activeRows = rows.filter((row) => row.atSec <= currentSec && (row.untilSec === undefined || currentSec < row.untilSec));
  const cardConfig = card ?? defaultCard;
  const contentScroll =
    rowPushes && rowPushes.length > 0
      ? rowPushOffsetAt(currentSec, fps, rowPushes)
      : scrollOffsetAt(currentSec, scroll);
  const palette = {...DEFAULT_CODEX_SESSION_THEME, ...theme};
  const cardAction = cardConfig.modelAction ? actionParts(cardConfig.modelAction) : null;
  const activeTopBarTitle = topBarTitleAtTime(currentSec, topBarTitle, topBarTitleSteps);
  const showBottomRight = currentSec >= bottomRightAtSec;
  const showFooter = currentSec >= footerAtSec;
  const cursorBlinkVisible = blinkCursorVisibleAt(frame, fps);

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
        <span style={{marginLeft: 10}}>{activeTopBarTitle}</span>
      </div>

      <div
        style={{
          position: 'absolute',
          inset: '44px 0 0 0',
          overflow: 'hidden',
          padding: '16px 12px 68px 12px',
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
              const isPlaceholder = !step.command;
              const showCursor = isLastVisible && currentSec < cardAtSec && cursorBlinkVisible;
              const fullCommand = step.command ?? '';
              const displayCommand = isLastVisible ? typedText : fullCommand;

              if (isPlaceholder && !isLastVisible) {
                return null;
              }

              if (step.bracketed) {
                return (
                  <div key={`${step.atSec}-${index}`} style={{marginBottom: 10}}>
                    <span style={{fontWeight: 500}}>[{step.prompt} % </span>
                    <span style={{fontWeight: 500}}>{displayCommand}</span>
                    {showCursor ? <span style={{color: palette.cursor, fontWeight: 700}}>{blockCursor}</span> : null}
                    <span style={{fontWeight: 500}}>]</span>
                  </div>
                );
              }

              return (
                <div key={`${step.atSec}-${index}`} style={{marginBottom: 10}}>
                  <span style={{fontWeight: 500}}>{step.prompt} % </span>
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
                <span>
                  {row.parts
                    ? renderRowParts({
                        parts: row.parts,
                        theme: palette,
                        frame,
                        fps,
                        rowAtSec: row.atSec,
                        rowAnimation: row.animation,
                      })
                    : null}
                </span>
              </div>
            );
          })}

        </div>
      </div>

      {showFooter ? (
        <div
          style={{
            position: 'absolute',
            left: 12,
            bottom: 8,
            color: palette.mutedText,
            fontSize: 18,
            lineHeight: 1.28,
          }}
        >
          {footerLines.map((line, index) => (
            <div
              key={`${line.glyph}-${line.text}`}
              style={{display: 'flex', gap: 10, marginBottom: index === footerLines.length - 1 ? 0 : 8}}
            >
              <span style={{width: 20}}>{line.glyph}</span>
              <span>{line.text}</span>
            </div>
          ))}
        </div>
      ) : null}

      {showBottomRight ? (
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
      ) : null}
    </AbsoluteFill>
  );
};
