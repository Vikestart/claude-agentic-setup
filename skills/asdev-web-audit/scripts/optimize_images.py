"""Convert PNG/JPEG to WebP and report the saving.

Two deliberate differences from the version this replaces, both about not
damaging your assets:

  * It is a DRY RUN by default. The old one rewrote every image in the tree the
    moment you ran it, with no preview and no confirmation. Pass --apply to
    write.
  * PNG converts to LOSSLESS WebP. The old one re-encoded everything at quality
    80, which is fine for photographs and visibly destroys UI screenshots,
    logos, and anything containing text. JPEG - already lossy - converts at
    --quality (default 82).

Originals are never deleted: the .webp is written alongside so you can update
references and remove the source yourself once the markup points at the new
file. A conversion that comes out larger than the source is skipped.

Requires Pillow (`pip install Pillow`). Run from a project root.
"""

from __future__ import annotations

import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import base_parser, iter_files, read_text, ReadError  # noqa: E402

SOURCE_EXTS = (".png", ".jpg", ".jpeg")
CODE_EXTS = (".html", ".htm", ".php", ".js", ".ts", ".css")

# Icons whose format is dictated by the platform, not by us: iOS ignores WebP
# for apple-touch-icon, and favicons need the broadest possible support.
PLATFORM_ICONS = re.compile(r"(?:^|/)(?:favicon|apple-touch-icon)[\w-]*\.\w+$",
                            re.IGNORECASE)


def encode(img, lossless: bool, quality: int) -> bytes:
    buf = io.BytesIO()
    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode == "CMYK":
        img = img.convert("RGB")
    if lossless:
        img.save(buf, "WEBP", lossless=True, method=6)
    else:
        img.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


def find_references(root: str, basename: str) -> int:
    hits = 0
    for rel in iter_files(CODE_EXTS, root, respect_scope=False):
        try:
            if basename in read_text(os.path.join(root, rel)):
                hits += 1
        except ReadError:
            continue
    return hits


def main() -> None:
    parser = base_parser("Convert PNG/JPEG to WebP (dry run unless --apply).")
    parser.add_argument("--apply", action="store_true",
                        help="actually write .webp files (default: preview only)")
    parser.add_argument("--quality", type=int, default=82, metavar="N",
                        help="JPEG->WebP quality, 1-100 (default: 82). "
                             "PNG is always lossless.")
    parser.add_argument("--force", action="store_true",
                        help="re-encode even when an up-to-date .webp exists")
    args = parser.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required: pip install Pillow", file=sys.stderr)
        sys.exit(2)

    root = args.path
    sources = iter_files(SOURCE_EXTS, root)
    if not sources:
        print("No PNG/JPEG images found.")
        sys.exit(0)

    converted = skipped = 0
    total_before = total_after = 0
    rows: list[str] = []

    for rel in sources:
        if PLATFORM_ICONS.search(rel):
            skipped += 1
            continue
        path = os.path.join(root, rel)
        target_rel = os.path.splitext(rel)[0] + ".webp"
        target = os.path.join(root, target_rel)
        lossless = rel.lower().endswith(".png")

        if (os.path.exists(target) and not args.force
                and os.path.getmtime(target) >= os.path.getmtime(path)):
            skipped += 1
            continue

        before = os.path.getsize(path)
        try:
            with Image.open(path) as img:
                data = encode(img, lossless, args.quality)
        except Exception as exc:  # Pillow raises a wide variety here
            rows.append(f"  [ERROR]  {rel}: {exc}")
            continue

        after = len(data)
        if after >= before:
            rows.append(f"  [NO GAIN] {rel}: webp would be "
                        f"{after / 1024:.0f}KB vs {before / 1024:.0f}KB - skipped")
            skipped += 1
            continue

        total_before += before
        total_after += after
        converted += 1
        pct = (before - after) / before * 100
        mode = "lossless" if lossless else f"q{args.quality}"
        rows.append(f"  {rel} -> {os.path.basename(target_rel)}  "
                    f"{before / 1024:.0f}KB -> {after / 1024:.0f}KB "
                    f"(-{pct:.0f}%, {mode})")

        if args.apply:
            with open(target, "wb") as fh:
                fh.write(data)
            refs = find_references(root, os.path.basename(rel))
            if refs:
                rows.append(f"      note: {os.path.basename(rel)} is still "
                            f"referenced in {refs} file(s) - update them to "
                            f"{os.path.basename(target_rel)}")

    verb = "Converted" if args.apply else "Would convert"
    print(f"=== optimize_images: {verb} {converted}, skipped {skipped} "
          f"({len(sources)} source images) ===")
    cap = args.max or 0
    shown = rows if cap == 0 else rows[:cap]
    for row in shown:
        print(row)
    if len(rows) > len(shown):
        print(f"  ... +{len(rows) - len(shown)} more (--max 0 to list all)")

    if total_before:
        saved = total_before - total_after
        print(f"Total: {total_before / 1048576:.2f}MB -> "
              f"{total_after / 1048576:.2f}MB "
              f"(saves {saved / 1048576:.2f}MB, {saved / total_before * 100:.0f}%)")
    if not args.apply and converted:
        print("Dry run - nothing written. Re-run with --apply to convert.")

    sys.exit(0)


if __name__ == "__main__":
    main()
