"""Apply desktop TTF defaults, including numeric colons in Sans and Serif.

Requires fonttools. Run again after replacing fonts with upstream builds.
"""

from collections import Counter
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from fontTools.otlLib.builder import buildCoverage, buildLookup
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables import otTables


PACKAGES = Path(__file__).resolve().parents[1] / "packages"
NUMERIC_COLON_FAMILIES = {"plex-sans", "plex-serif"}
TEXT_DEFAULT_FAMILIES = {"plex-sans", "plex-serif", "plex-mono"}


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


def numeric_glyphs(font):
    cmap = font.getBestCmap()
    digits = {cmap[ord(digit)] for digit in "0123456789"}
    substitutions = {}

    # Number features run before our lookup. Include their oldstyle, slashed
    # zero, and other digit forms so the context still matches afterward.
    for lookup in font["GSUB"].table.LookupList.Lookup:
        for subtable in lookup.SubTable:
            if lookup.LookupType == 7:
                subtable = subtable.ExtSubTable

            for source, target in getattr(subtable, "mapping", {}).items():
                substitutions.setdefault(source, set()).add(target)

            for source, targets in getattr(subtable, "alternates", {}).items():
                substitutions.setdefault(source, set()).update(targets)

    while True:
        expanded = digits | {
            target for source in digits for target in substitutions.get(source, ())
        }

        if expanded == digits:
            return digits

        digits = expanded


def add_numeric_colon(font):
    cmap = font.getBestCmap()
    colon = cmap[ord(":")]
    ratio = cmap[0x2236]
    digits = numeric_glyphs(font)
    gsub = font["GSUB"].table
    features = gsub.FeatureList.FeatureRecord
    calt_features = [record.Feature for record in features if record.FeatureTag == "calt"]

    for feature in calt_features:
        for index in feature.LookupListIndex:
            lookup = gsub.LookupList.Lookup[index]

            if lookup.LookupType != 8 or lookup.LookupFlag or len(lookup.SubTable) != 1:
                continue

            subtable = lookup.SubTable[0]

            if (
                subtable.Coverage.glyphs == [colon]
                and subtable.Substitute == [ratio]
                and len(subtable.BacktrackCoverage) == 1
                and len(subtable.LookAheadCoverage) == 1
                and set(subtable.BacktrackCoverage[0].glyphs) == digits
                and set(subtable.LookAheadCoverage[0].glyphs) == digits
            ):
                return False

    # Equivalent feature rule: rsub @digits colon' @digits by uni2236;
    glyph_map = font.getReverseGlyphMap()
    subtable = otTables.ReverseChainSingleSubst()
    subtable.Format = 1
    subtable.Coverage = buildCoverage([colon], glyph_map)
    subtable.BacktrackCoverage = [buildCoverage(digits, glyph_map)]
    subtable.BacktrackGlyphCount = 1
    subtable.LookAheadCoverage = [buildCoverage(digits, glyph_map)]
    subtable.LookAheadGlyphCount = 1
    subtable.Substitute = [ratio]
    subtable.GlyphCount = 1
    lookup_index = len(gsub.LookupList.Lookup)
    gsub.LookupList.Lookup.append(buildLookup([subtable]))
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)

    language_systems = []

    for record in gsub.ScriptList.ScriptRecord:
        if record.Script.DefaultLangSys is not None:
            language_systems.append(record.Script.DefaultLangSys)

        language_systems.extend(item.LangSys for item in record.Script.LangSysRecord)

    if calt_features:
        for feature in calt_features:
            feature.LookupListIndex.append(lookup_index)
            feature.LookupCount = len(feature.LookupListIndex)
    else:
        if getattr(gsub, "FeatureVariations", None) is not None:
            raise ValueError("Variable GSUB features are not supported")

        # Feature records must remain sorted. Adjust references to shifted ones.
        feature_index = next(
            (index for index, record in enumerate(features) if record.FeatureTag > "calt"),
            len(features),
        )
        record = otTables.FeatureRecord()
        record.FeatureTag = "calt"
        record.Feature = otTables.Feature()
        record.Feature.FeatureParams = None
        record.Feature.LookupListIndex = [lookup_index]
        record.Feature.LookupCount = 1
        features.insert(feature_index, record)
        gsub.FeatureList.FeatureCount = len(features)

        for language in language_systems:
            language.FeatureIndex = [
                index + (index >= feature_index) for index in language.FeatureIndex
            ]

            if language.ReqFeatureIndex != 0xFFFF and language.ReqFeatureIndex >= feature_index:
                language.ReqFeatureIndex += 1

    calt_indexes = {index for index, record in enumerate(features) if record.FeatureTag == "calt"}

    for language in language_systems:
        language.FeatureIndex = sorted(set(language.FeatureIndex) | calt_indexes)
        language.FeatureCount = len(language.FeatureIndex)

    return True


def customize_font(path):
    with TTFont(path, recalcBBoxes=False, recalcTimestamp=False) as font:
        gsub = font.get("GSUB")

        if gsub is None or gsub.table.FeatureList is None:
            return False

        italic_changed = enable_italic_ss02(font)
        ligatures_changed = disable_standard_ligatures(font)
        numeric_colon_changed = (
            add_numeric_colon(font) if path.parts[-5] in NUMERIC_COLON_FAMILIES else False
        )

        if not italic_changed and not ligatures_changed and not numeric_colon_changed:
            return False

        if not ligatures_changed and not numeric_colon_changed:
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


def use_text_as_regular(directory):
    changed = []

    if directory.parts[-4] not in TEXT_DEFAULT_FAMILIES:
        return changed

    for source in sorted(directory.glob("*-Text*.ttf")):
        variant = source.stem.rsplit("-", 1)[1]

        if variant not in ("Text", "TextItalic"):
            continue

        target_variant = "Regular" if variant == "Text" else "Italic"
        target = source.with_name(f"{source.stem.rsplit('-', 1)[0]}-{target_variant}.ttf")

        with TTFont(source, recalcBBoxes=False, recalcTimestamp=False) as font, TTFont(target) as regular:
            # Keep the normal family's identity and style links so applications
            # requesting Regular/400 receive the heavier Text design.
            font["name"] = deepcopy(regular["name"])
            font["OS/2"].usWeightClass = 400
            font["OS/2"].fsSelection = regular["OS/2"].fsSelection
            font["head"].macStyle = regular["head"].macStyle

            if "DSIG" in font and font["DSIG"].usNumSigs:
                del font["DSIG"]

            output = BytesIO()
            font.save(output)

        data = output.getvalue()

        if target.read_bytes() != data:
            target.write_bytes(data)
            changed.append(target)

    return changed


def main():
    changed = set()

    for path in sorted(PACKAGES.glob("plex-*/fonts/complete/ttf/*.ttf")):
        if customize_font(path):
            changed.add(path)

    # Promote Text only after its glyph defaults and contextual rules are ready.
    for directory in sorted(PACKAGES.glob("plex-*/fonts/complete/ttf")):
        changed.update(use_text_as_regular(directory))

    counts = Counter(path.parts[-5] for path in changed)

    print("Updated desktop fonts:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
