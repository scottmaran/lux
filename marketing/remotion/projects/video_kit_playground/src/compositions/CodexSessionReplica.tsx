import React from 'react';
import {CodexSession, CODEX_SESSION_SOURCE_REPLICA} from '../../../../packages/video-kit/src';

export const CodexSessionReplica: React.FC = () => {
  return (
    <CodexSession
      commandSteps={CODEX_SESSION_SOURCE_REPLICA.commandSteps}
      cardAtSec={CODEX_SESSION_SOURCE_REPLICA.cardAtSec}
      card={CODEX_SESSION_SOURCE_REPLICA.card}
      rows={CODEX_SESSION_SOURCE_REPLICA.rows}
      scroll={CODEX_SESSION_SOURCE_REPLICA.scroll}
      rowPushes={CODEX_SESSION_SOURCE_REPLICA.rowPushes}
      topBarTitle={CODEX_SESSION_SOURCE_REPLICA.topBarTitle}
      topBarTitleSteps={CODEX_SESSION_SOURCE_REPLICA.topBarTitleSteps}
      bottomRightLabel={CODEX_SESSION_SOURCE_REPLICA.bottomRightLabel}
      bottomRightAtSec={CODEX_SESSION_SOURCE_REPLICA.bottomRightAtSec}
      footerAtSec={CODEX_SESSION_SOURCE_REPLICA.footerAtSec}
      footerInputAtSec={CODEX_SESSION_SOURCE_REPLICA.footerInputAtSec}
      footerLines={CODEX_SESSION_SOURCE_REPLICA.footerLines}
    />
  );
};
