# IBM Plex desktop fonts

Personal desktop fork of [IBM Plex](https://github.com/IBM/plex), containing complete TrueType fonts only.

| Family | TTF files |
| --- | --- |
| Sans | [packages/plex-sans/fonts/complete/ttf](packages/plex-sans/fonts/complete/ttf/) |
| Serif | [packages/plex-serif/fonts/complete/ttf](packages/plex-serif/fonts/complete/ttf/) |
| Mono | [packages/plex-mono/fonts/complete/ttf](packages/plex-mono/fonts/complete/ttf/) |
| Math | [packages/plex-math/fonts/complete/ttf](packages/plex-math/fonts/complete/ttf/) |

Open the `.ttf` files in your desktop font manager to install them. Reinstall them after updating existing fonts.

All Sans, Serif, and Mono italics use the single-storey `g` and its accented forms by default. The `ss02` alternates are built into their character mappings, so no application feature setting is needed.

Standard ligatures (`liga`), such as `fi`, `fl`, `ff`, `ffi`, and `ffl`, are disabled in the font binaries.

After replacing TTFs with upstream versions, reapply these defaults:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/customize-fonts.py
```

The fonts retain their original licenses; see [LICENSE.txt](LICENSE.txt) and the license files in each package.
