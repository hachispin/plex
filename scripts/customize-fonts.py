"""Apply desktop TTF defaults: single-storey italic g and no standard ligatures.

Requires fonttools. Run again after replacing fonts with upstream builds.
"""

from collections import Counter
from io import BytesIO
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable


PACKAGES = Path(__file__).resolve().parents[1] / "packages"


def enable_italic_ss02(font):
    if not font["OS/2"].fsSelection & 1:
        return False

    substitutions = {}
    gsub = font["GSUB"].table
    lookup_indexes = {
        index
        for feature in gsub.FeatureList.FeatureRecord
        if feature.FeatureTag == "ss02"
        for index in feature.Feature.LookupListIndex
    }

    for index in lookup_indexes:
        lookup = gsub.LookupList.Lookup[index]

        for subtable in lookup.SubTable:
            if lookup.LookupType == 7:
                subtable = subtable.ExtSubTable

            mapping = getattr(subtable, "mapping", None)

            if mapping is None:
                raise ValueError("Unsupported ss02 substitution")

            substitutions.update(mapping)

    changed = False

    # Update Unicode and legacy maps while retaining the original glyphs.
    for table in font["cmap"].tables:
        for character, glyph in table.cmap.items():
            if glyph in substitutions:
                table.cmap[character] = substitutions[glyph]
                changed = True

    return changed


def disable_standard_ligatures(font):
    changed = False

    # Keep feature indices and lookups intact for other OpenType features.
    for feature in font["GSUB"].table.FeatureList.FeatureRecord:
        if feature.FeatureTag == "liga" and feature.Feature.LookupListIndex:
            feature.Feature.LookupListIndex = []
            feature.Feature.LookupCount = 0
            changed = True

    return changed


def customize_font(path):
    with TTFont(path, recalcBBoxes=False, recalcTimestamp=False) as font:
        gsub = font.get("GSUB")

        if gsub is None or gsub.table.FeatureList is None:
            return False

        italic_changed = enable_italic_ss02(font)
        ligatures_changed = disable_standard_ligatures(font)

        if not italic_changed and not ligatures_changed:
            return False

        if not ligatures_changed:
            # Avoid recompiling feature tables when only character maps change.
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

    for path in sorted(PACKAGES.glob("plex-*/fonts/complete/ttf/*.ttf")):
        if customize_font(path):
            changed[path.parts[-5]] += 1

    print("Updated desktop fonts:", dict(sorted(changed.items())))


if __name__ == "__main__":
    main()
