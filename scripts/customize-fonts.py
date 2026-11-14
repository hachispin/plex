"""Apply desktop TTF defaults, including numeric colons in Sans and Serif.

Requires fonttools. Run again after replacing fonts with upstream builds.
"""

from collections import Counter
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from fontTools.otlLib.builder import buildCoverage, buildLookup, buildValue
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.ttLib.tables import otTables


FONTS = Path(__file__).resolve().parents[1] / "fonts"
NUMERIC_COLON_FAMILIES = {"sans", "serif"}
TEXT_DEFAULT_FAMILIES = {"sans", "serif", "mono"}
SLASH_KERNING_FAMILIES = {"sans", "serif"}
ANGLE_KERNING_FAMILIES = {"sans", "serif"}


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


def enable_standard_ligatures(font):
    cmap = font.getBestCmap()
    standard_glyphs = {
        cmap[codepoint] for codepoint in range(0xFB00, 0xFB07) if codepoint in cmap
    }
    gsub = font["GSUB"].table
    indexes = set()

    # Recover the original standard-ligature lookups without enabling the
    # separate ligature lookups used for combining-mark composition.
    for index, lookup in enumerate(gsub.LookupList.Lookup):
        for subtable in lookup.SubTable:
            lookup_type = lookup.LookupType

            if lookup_type == 7:
                lookup_type = subtable.ExtensionLookupType
                subtable = subtable.ExtSubTable

            if lookup_type != 4:
                continue

            if any(
                record.LigGlyph in standard_glyphs
                for records in subtable.ligatures.values()
                for record in records
            ):
                indexes.add(index)

    if not indexes:
        raise ValueError("No standard ligature substitutions found")

    changed = False

    for feature in gsub.FeatureList.FeatureRecord:
        if feature.FeatureTag != "liga":
            continue

        enabled = sorted(set(feature.Feature.LookupListIndex) | indexes)

        if feature.Feature.LookupListIndex != enabled:
            feature.Feature.LookupListIndex = enabled
            feature.Feature.LookupCount = len(enabled)
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


def set_kerning_pair(subtable, first, second, value1, value2, glyph_map):
    pairs = dict(zip(subtable.Coverage.glyphs, subtable.PairSet))

    if first not in pairs:
        pairs[first] = otTables.PairSet()
        pairs[first].PairValueRecord = []

    pair_set = pairs[first]
    target = next(
        (pair for pair in pair_set.PairValueRecord if pair.SecondGlyph == second),
        None,
    )

    if target is not None and target.Value1 == value1 and target.Value2 == value2:
        return False

    if target is not None:
        pair_set.PairValueRecord.remove(target)

    replacement = otTables.PairValueRecord()
    replacement.SecondGlyph = second
    replacement.Value1 = deepcopy(value1)
    replacement.Value2 = deepcopy(value2)
    pair_set.PairValueRecord.append(replacement)
    pair_set.PairValueRecord.sort(key=lambda pair: glyph_map[pair.SecondGlyph])
    pair_set.PairValueCount = len(pair_set.PairValueRecord)
    subtable.Coverage = buildCoverage(pairs, glyph_map)
    subtable.PairSet = [pairs[glyph] for glyph in subtable.Coverage.glyphs]
    subtable.PairSetCount = len(subtable.PairSet)

    return True


def match_repeated_slash_kerning(font):
    gpos = font.get("GPOS")

    if gpos is None or gpos.table.FeatureList is None:
        return False

    cmap = font.getBestCmap()
    slash = cmap[ord("/")]
    backslash = cmap[ord("\\")]
    glyph_map = font.getReverseGlyphMap()
    lookups = {
        index
        for feature in gpos.table.FeatureList.FeatureRecord
        if feature.FeatureTag == "kern"
        for index in feature.Feature.LookupListIndex
    }
    changed = False

    for index in sorted(lookups):
        lookup = gpos.table.LookupList.Lookup[index]

        if lookup.LookupType not in (2, 9):
            continue

        for subtable in lookup.SubTable:
            if lookup.LookupType == 9:
                if subtable.ExtensionLookupType != 2:
                    continue

                subtable = subtable.ExtSubTable

            if subtable.Format != 1 or slash not in subtable.Coverage.glyphs:
                continue

            pairs = dict(zip(subtable.Coverage.glyphs, subtable.PairSet))
            source = next(
                (pair for pair in pairs[slash].PairValueRecord if pair.SecondGlyph == slash),
                None,
            )

            if source is None:
                continue

            changed = set_kerning_pair(
                subtable, backslash, backslash, source.Value1, source.Value2, glyph_map
            ) or changed

    return changed


def kern_repeated_angles(font):
    gpos = font.get("GPOS")

    if gpos is None or gpos.table.FeatureList is None:
        return False

    lookups = {
        index
        for feature in gpos.table.FeatureList.FeatureRecord
        if feature.FeatureTag == "kern"
        for index in feature.Feature.LookupListIndex
    }
    glyph_map = font.getReverseGlyphMap()
    cmap = font.getBestCmap()
    value = buildValue({"XAdvance": -round(font["head"].unitsPerEm * 0.1)})

    # Use the final pair-positioning lookup so these explicit pairs take
    # precedence over its class-based fallback without replacing other pairs.
    for index in sorted(lookups, reverse=True):
        lookup = gpos.table.LookupList.Lookup[index]

        if lookup.LookupType != 2:
            continue

        for subtable in lookup.SubTable:
            if subtable.Format != 1 or subtable.ValueFormat1 != 4 or subtable.ValueFormat2 != 0:
                continue

            changed = False

            for character in "<>":
                glyph = cmap[ord(character)]
                changed = set_kerning_pair(subtable, glyph, glyph, value, None, glyph_map) or changed

            return changed

    raise ValueError("No suitable kerning lookup for repeated angle symbols")


def customize_font(path):
    with TTFont(path, recalcBBoxes=False, recalcTimestamp=False) as font:
        gsub = font.get("GSUB")

        if gsub is None or gsub.table.FeatureList is None:
            return False

        italic_changed = enable_italic_ss02(font)
        ligatures_changed = (
            enable_standard_ligatures(font)
            if path.parent.name == "serif"
            else disable_standard_ligatures(font)
        )
        numeric_colon_changed = (
            add_numeric_colon(font) if path.parent.name in NUMERIC_COLON_FAMILIES else False
        )
        kerning_changed = (
            match_repeated_slash_kerning(font) if path.parent.name in SLASH_KERNING_FAMILIES else False
        )
        angle_kerning_changed = (
            kern_repeated_angles(font) if path.parent.name in ANGLE_KERNING_FAMILIES else False
        )
        kerning_changed = kerning_changed or angle_kerning_changed

        if not any((italic_changed, ligatures_changed, numeric_colon_changed, kerning_changed)):
            return False

        if not ligatures_changed and not numeric_colon_changed:
            # Avoid recompiling feature tables when only character maps change.
            original_gsub = DefaultTable("GSUB")
            original_gsub.data = font.reader["GSUB"]
            font["GSUB"] = original_gsub

        if not kerning_changed and "GPOS" in font:
            original_gpos = DefaultTable("GPOS")
            original_gpos.data = font.reader["GPOS"]
            font["GPOS"] = original_gpos

        if "DSIG" in font and font["DSIG"].usNumSigs:
            del font["DSIG"]

        output = BytesIO()
        font.save(output)

    path.write_bytes(output.getvalue())

    return True


def use_text_as_regular(directory):
    changed = []

    if directory.name not in TEXT_DEFAULT_FAMILIES:
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

    for path in sorted(FONTS.glob("*/*.ttf")):
        if customize_font(path):
            changed.add(path)

    # Promote Text only after its glyph defaults and contextual rules are ready.
    for directory in sorted(FONTS.iterdir()):
        if directory.is_dir():
            changed.update(use_text_as_regular(directory))

    counts = Counter(path.parent.name for path in changed)

    print("Updated desktop fonts:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()
