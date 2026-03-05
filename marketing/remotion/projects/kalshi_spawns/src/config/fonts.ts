// import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
// import {loadFont as loadJetBrainsMono} from '@remotion/google-fonts/JetBrainsMono';

import {loadFont as loadInter} from '@remotion/google-fonts/Montserrat';
import {loadFont as loadJetBrainsMono} from '@remotion/google-fonts/Montserrat';

export const {fontFamily: interFontFamily} = loadInter('normal', {
  weights: ['400', '600', '700'],
  subsets: ['latin'],
});

export const {fontFamily: jetBrainsMonoFamily} = loadJetBrainsMono('normal', {
  weights: ['400', '700'],
  subsets: ['latin'],
});
