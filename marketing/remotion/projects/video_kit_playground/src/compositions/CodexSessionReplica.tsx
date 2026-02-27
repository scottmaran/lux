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
      topBarTitle={CODEX_SESSION_SOURCE_REPLICA.topBarTitle}
      bottomRightLabel={CODEX_SESSION_SOURCE_REPLICA.bottomRightLabel}
    />
  );
};
