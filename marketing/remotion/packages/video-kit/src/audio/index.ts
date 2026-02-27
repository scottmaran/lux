export type AudioCue = {
  id: string;
  fileName: string;
  defaultVolume?: number;
};

export const EMPTY_AUDIO_LIBRARY: AudioCue[] = [];
