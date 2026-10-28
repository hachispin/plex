"""Make ss02 glyphs the defaults in the supplied italic font binaries.

Requires fonttools[woff]. Run again after replacing fonts with upstream builds.
"""

from collections import Counter
from io import BytesIO
from pathlib import Path
import struct

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable


PACKAGES = Path(__file__).resolve().parents[1] / "packages"
FONT_FORMATS = {".ttf", ".otf", ".woff", ".woff2"}


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

        # Reading features and glyph names decompiles GSUB and CFF. Preserve
        # their original bytes so only character mappings and checksums change.
        for tag in ("GSUB", "CFF "):
            if tag in font:
                original_table = DefaultTable(tag)
                original_table.data = font.reader[tag]
                font[tag] = original_table

        if "DSIG" in font and font["DSIG"].usNumSigs:
            del font["DSIG"]

        output = BytesIO()
        font.save(output)

    path.write_bytes(output.getvalue())

    return True


def update_eot(path):
    # EOT header layout: https://www.w3.org/submissions/EOT/
    # Reuse its metadata and embed the matching updated TTF without compression.
    original = path.read_bytes()
    size, font_size, version, flags = struct.unpack_from("<IIII", original)

    if size != len(original) or not 0 < font_size < size:
        raise ValueError(f"Invalid EOT lengths: {path}")

    if version != 0x00020002 or flags & ~0x00000004:
        raise ValueError(f"Unsupported EOT version or flags: {path}")

    font_path = path.parent.parent / "ttf" / path.with_suffix(".ttf").name
    font_data = font_path.read_bytes()
    header = bytearray(original[:-font_size])

    with TTFont(BytesIO(font_data)) as font:
        # Verify that the preserved EOT names describe this TTF.
        offset = 82

        for name_id in (1, 2, 5, 4):
            name_size = struct.unpack_from("<H", header, offset)[0]
            name = header[offset + 2:offset + 2 + name_size].decode("utf-16-le")

            if name != font["name"].getDebugName(name_id):
                raise ValueError(f"EOT/TTF name mismatch: {path}")

            offset += 2 + name_size + 2

        struct.pack_into("<II", header, 0, len(header) + len(font_data), len(font_data))
        struct.pack_into("<I", header, 12, flags & ~0x00000004)
        struct.pack_into("<I", header, 60, font["head"].checkSumAdjustment)

    updated = header + font_data

    if updated == original:
        return False

    path.write_bytes(updated)

    return True


def main():
    changed = Counter()

    for path in sorted(PACKAGES.glob("plex-*/fonts/**/*Italic*")):
        if path.suffix in FONT_FORMATS and enable_ss02(path):
            changed[path.suffix] += 1

    for path in sorted(PACKAGES.glob("plex-*/fonts/**/*.eot")):
        if "Italic" in path.name and update_eot(path):
            changed[path.suffix] += 1

    print("Updated italic fonts:", dict(sorted(changed.items())))


if __name__ == "__main__":
    main()
