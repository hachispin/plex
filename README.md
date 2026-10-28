# IBM Plex desktop fonts

Personal desktop fork of [IBM Plex](https://github.com/IBM/plex), containing complete TrueType fonts only.

| Family | TTF files |
| --- | --- |
| Sans | [packages/plex-sans/fonts/complete/ttf](packages/plex-sans/fonts/complete/ttf/) |
| Serif | [packages/plex-serif/fonts/complete/ttf](packages/plex-serif/fonts/complete/ttf/) |
| Mono | [packages/plex-mono/fonts/complete/ttf](packages/plex-mono/fonts/complete/ttf/) |
| Math | [packages/plex-math/fonts/complete/ttf](packages/plex-math/fonts/complete/ttf/) |

Open the `.ttf` files in your desktop font manager to install them. Reinstall them after updating existing fonts.

The ordinary Sans, Serif, and Mono families use the heavier Text (450) design for Regular and Italic. These faces retain their original names and weight-400 metadata so applications selecting the default family style get the Text appearance automatically. The separately named Text files retain their 450 metadata.

All Sans, Serif, and Mono italics use the single-storey `g` and its accented forms by default. The `ss02` alternates are built into their character mappings, so no application feature setting is needed.

Standard ligatures (`liga`), such as `fi`, `fl`, `ff`, `ffi`, and `ffl`, are disabled in the font binaries.

Sans and Serif apply the same pair kerning to repeated backslashes as repeated forward slashes, so runs such as `///` and `\\\` receive matching spacing adjustments.

Sans and Serif use the existing ratio glyph (`∶`) for a colon directly between digits, as in `1:1` or `12:34`. This contextual alternate (`calt`) is enabled by default; other colons keep their usual appearance. It also works with alternate digit styles. Mono and Math do not apply this substitution.

After replacing TTFs with upstream versions, reapply these defaults:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/customize-fonts.py
```

To verify the font defaults, run `python3 -m unittest discover -s tests`. Shaping checks require the HarfBuzz `hb-shape` command.

The fonts retain their original licenses; see [LICENSE.txt](LICENSE.txt) and the license files in each package.
