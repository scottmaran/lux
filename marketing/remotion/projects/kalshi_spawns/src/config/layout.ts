import {HEIGHT, WIDTH} from './timing';

const insetWidth = Math.round(WIDTH * 0.75);
const insetHeight = Math.round(HEIGHT * 0.8);
const commandWidth = Math.round(WIDTH * 0.62);
const commandHeight = Math.round(HEIGHT * 0.62);

export const INSET_DASHBOARD_WINDOW = {
  x: Math.floor((WIDTH - insetWidth) / 2),
  y: Math.floor((HEIGHT - insetHeight) / 2),
  width: insetWidth,
  height: insetHeight,
} as const;

export const COMMAND_TERMINAL_WINDOW = {
  x: Math.floor((WIDTH - commandWidth) / 2),
  y: 170,
  width: commandWidth,
  height: commandHeight,
} as const;
