const serifUnicodeRanges = require('./unicodes/serif');
const monoUnicodeRanges = require('./unicodes/mono');

const families = [
  {
    type: 'Mono',
    name: 'IBM Plex Mono',
    packageName: 'plex-mono',
    hasItalic: true,
    unicodes: monoUnicodeRanges.map(({ type }) => type),
  },
  {
    type: 'Sans',
    name: 'IBM Plex Sans',
    packageName: 'plex-sans',
    hasItalic: true,
    unicodes: ['Latin1', 'Latin2', 'Latin3', 'Pi', 'Cyrillic', 'Greek'],
  },
  {
    type: 'Serif',
    name: 'IBM Plex Serif',
    packageName: 'plex-serif',
    hasItalic: true,
    unicodes: serifUnicodeRanges.map(({ type }) => type),
  },
  {
    type: 'Math',
    name: 'IBM Plex Math',
    packageName: 'plex-math',
    hasItalic: false,
    unicodes: [],
    weights: ['Regular'],
  },
];

module.exports = families;
