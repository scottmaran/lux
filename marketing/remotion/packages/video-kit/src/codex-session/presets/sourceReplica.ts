import type {CodexSessionPreset, CodexSessionRow} from '../types';

const row = (entry: CodexSessionRow): CodexSessionRow => entry;

export const CODEX_SESSION_SOURCE_REPLICA: CodexSessionPreset = {
  title: 'CodexSessionSourceReplica',
  width: 928,
  height: 598,
  durationInFrames: 4022,
  topBarTitle: 'lux_workspace - docker-compose < lux shim exec codex --- 82x24',
  bottomRightLabel: '100% context left',
  commandSteps: [
    {
      atSec: 0,
      prompt: 'scottmaran@MacBookAir lux_workspace',
      bracketed: false,
    },
    {
      atSec: 5.8,
      prompt: 'scottmaran@MacBookAir lux_workspace',
      command: 'lux',
      typingDurationSec: 0.8,
      bracketed: false,
    },
    {
      atSec: 8.7,
      prompt: 'scottmaran@MacBookAir lux_workspace',
      command: 'lux',
      typingDurationSec: 0.05,
      bracketed: true,
    },
    {
      atSec: 9.4,
      prompt: 'scottmaran@MacBookAir lux_workspace',
      command: 'codex',
      typingDurationSec: 0.8,
      bracketed: true,
    },
  ],
  cardAtSec: 9.9,
  rows: [
    row({
      atSec: 10.8,
      glyph: 'arrow',
      parts: [{text: 'Using ESPN.com only, find the most recent completed Boston Celtics game and return:'}],
    }),
    row({atSec: 10.9, indent: 34, parts: [{text: '- final score'}]}),
    row({atSec: 11.0, indent: 34, parts: [{text: '- exact ESPN game URL'}]}),
    row({atSec: 11.1, indent: 34, parts: [{text: '- exact page title text from that ESPN page'}]}),
    row({atSec: 11.2, indent: 34, parts: [{text: '- one sentence from the ESPN game recap (quoted)'}]}),

    row({
      atSec: 12,
      glyph: 'dot',
      parts: [
        {text: 'Working', bold: true},
        {text: ' (2s * esc to interrupt)', tone: 'muted'},
      ],
      style: {color: '#9B9B9D'},
    }),

    row({
      atSec: 21.4,
      glyph: 'hollow',
      parts: [
        {text: 'Starting', bold: true},
        {text: ' ESPN Celtics game lookup', bold: true},
        {text: ' (6s * esc to interrupt)', tone: 'muted'},
      ],
    }),

    row({
      atSec: 25.4,
      glyph: 'dot',
      parts: [
        {
          text: "I'm going to check ESPN's Celtics schedule/results page first, then open the latest completed game page to capture the exact score, URL, title text, and a recap sentence verbatim.",
        },
      ],
    }),
    row({
      atSec: 26.2,
      glyph: 'dot',
      parts: [
        {text: 'Searched ', bold: true},
        {text: 'ESPN Boston Celtics schedule results 2025-26'},
      ],
    }),
    row({
      atSec: 27,
      glyph: 'hollow',
      parts: [
        {text: 'Querying', bold: true},
        {text: ' ESPN Celtics schedule ', tone: 'muted'},
        {text: '(10s * esc to interrupt)', tone: 'muted'},
      ],
    }),

    row({atSec: 29.4, kind: 'separator'}),

    row({
      atSec: 29.7,
      glyph: 'dot',
      parts: [
        {
          text: "I found ESPN's Celtics schedule page and I'm opening it now to pull the newest final result and its direct game link from ESPN.",
        },
      ],
    }),
    row({
      atSec: 30.6,
      glyph: 'dot',
      parts: [
        {text: 'Searched ', bold: true},
        {text: 'https://www.espn.com/nba/team/schedule/_/name/bos/season/2026'},
      ],
    }),
    row({
      atSec: 31.8,
      glyph: 'dot',
      parts: [
        {text: 'Searched ', bold: true},
        {text: 'https://www.espn.com/nba/team/schedule/_/name/bos/season/2026'},
      ],
    }),

    row({atSec: 33, kind: 'separator'}),

    row({
      atSec: 33.2,
      glyph: 'dot',
      parts: [
        {
          text: "The schedule shows the newest completed result as Feb 25 at Denver. Next I'm opening that linked ESPN game page to capture the exact URL, title, and recap sentence.",
        },
      ],
    }),
    row({
      atSec: 34.2,
      glyph: 'dot',
      parts: [
        {text: 'Searched ', bold: true},
        {text: 'https://www.espn.com/nba/game/_/gameId/401810702/celtics-nuggets'},
      ],
    }),
    row({
      atSec: 40.8,
      glyph: 'dot',
      parts: [
        {text: 'Searched ', bold: true},
        {text: 'https://www.espn.com/nba/recap/_/gameId/401810702'},
      ],
    }),
    row({
      atSec: 42,
      glyph: 'dot',
      parts: [
        {text: 'Planning', bold: true},
        {text: ' exact sentence quote (32s * esc to interrupt)', tone: 'muted'},
      ],
      style: {color: '#9B9B9D'},
    }),
    row({
      atSec: 54,
      glyph: 'dot',
      parts: [
        {text: 'Finalizing', bold: true},
        {text: ' ESPN content and citations (44s * esc to interrupt)', tone: 'muted'},
      ],
      style: {color: '#9B9B9D'},
    }),

    row({atSec: 58.8, kind: 'separator'}),

    row({
      atSec: 60.2,
      glyph: 'dot',
      parts: [
        {
          text: "I have the exact ESPN game and recap pages; I'm now compiling the requested fields exactly as shown on ESPN.",
        },
      ],
    }),
    row({
      atSec: 61,
      indent: 22,
      parts: [
        {text: '- Final score: '},
        {text: 'Denver Nuggets 103, Boston Celtics 84', bold: true},
        {text: ' (Final, February 25, 2026)'},
      ],
    }),
    row({
      atSec: 61.8,
      indent: 22,
      parts: [
        {text: '- Exact ESPN game URL: '},
        {text: 'https://www.espn.com/nba/game/_/gameId/401810702/celtics-nuggets', bold: true},
      ],
    }),
    row({
      atSec: 62.6,
      indent: 22,
      parts: [
        {text: '- Exact page title text: '},
        {text: 'Nuggets 103-84 Celtics (Feb 25, 2026) Final Score - ESPN', bold: true},
      ],
    }),
    row({
      atSec: 63.4,
      indent: 22,
      parts: [
        {text: '- One sentence from the ESPN recap: '},
        {
          text: '"Jaylen Brown returned to Boston\'s lineup after sitting out Tuesday night at Phoenix with a right knee contusion."',
          bold: true,
        },
      ],
    }),
    row({atSec: 64.4, kind: 'spacer'}),
    row({atSec: 64.6, indent: 22, parts: [{text: 'Sources (ESPN only):'}]}),
    row({atSec: 64.9, indent: 22, parts: [{text: 'https://www.espn.com/nba/team/schedule/_/name/bos/season/2026'}]}),
    row({atSec: 65.2, indent: 22, parts: [{text: 'https://www.espn.com/nba/game/_/gameId/401810702/celtics-nuggets'}]}),
    row({atSec: 65.5, indent: 22, parts: [{text: 'https://www.espn.com/nba/recap/_/gameId/401810702'}]}),
  ],
  scroll: [
    {atSec: 0, offset: 0},
    {atSec: 21, offset: 0},
    {atSec: 26, offset: 80},
    {atSec: 30, offset: 150},
    {atSec: 34, offset: 235},
    {atSec: 42, offset: 280},
    {atSec: 54, offset: 300},
    {atSec: 60, offset: 430},
    {atSec: 66, offset: 520},
  ],
};
