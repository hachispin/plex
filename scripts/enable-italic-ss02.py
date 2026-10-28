"""Make ss02 glyphs the defaults in the supplied italic desktop TTFs.

Requires fonttools. Run again after replacing fonts with upstream builds.
"""

from collections import Counter
from io import BytesIO
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable


PACKAGES = Path(__file__).resolve().parents[1] / "packages"


def enable_ss02(path):
    with TTFont(path, recalcBBoxes=False, recalcTimestamp=False) as font:
        if not font["OS/2"].fsSelection & 1:
            raise ValueError(f"Expected an italic font: {path}")

        substitutions = {}
        gsub = font.get("GSUB")

        if gsub is None or gsub.table.FeatureList is None:
            return False

        lookup_indexes = {
            index
            for feature in gsub.table.FeatureList.FeatureRecord
            if feature.FeatureTag == "ss02"
            for index in feature.Feature.LookupListIndex
        }

        for index in lookup_indexes:
            lookup = gsub.table.LookupList.Lookup[index]

            for subtable in lookup.SubTable:
                if lookup.LookupType == 7:
                    subtable = subtable.ExtSubTable

                mapping = getattr(subtable, "mapping", None)

                if mapping is None:
                    raise ValueError(f"Unsupported ss02 substitution in {path}")

                substitutions.update(mapping)

        changed = False

        # Update Unicode and legacy character maps, keeping the original glyphs
        # and OpenType features available in the font.
        for table in font["cmap"].tables:
            for character, glyph in table.cmap.items():
                if glyph in substitutions:
                    table.cmap[character] = substitutions[glyph]
                    changed = True

        if not changed:
            return False

        # Reading features decompiles GSUB. Preserve its original bytes so only
        # character mappings and checksums change.
        original_gsub = DefaultTable("GSUB")
        original_gsub.data = font.reader["GSUB"]
        font["GSUB"] = original_gsub

        if "DSIG" in font and font["DSIG"].usNumSigs:
            del font["DSIG"]

        output = BytesIO()
        font.save(output)

    path.write_bytes(output.getvalue())

    return True


def main():
    changed = Counter()

    for path in sorted(PACKAGES.glob("plex-*/fonts/complete/ttf/*Italic.ttf")):
        if enable_ss02(path):
            changed[path.suffix] += 1

    print("Updated italic fonts:", dict(sorted(changed.items())))


if __name__ == "__main__":
    main()
