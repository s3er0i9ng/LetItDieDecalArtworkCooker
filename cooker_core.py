"""Safe, standalone decal-art cooking engine for LET IT DIE.

This module never writes to the game directory. It reads three stock donor
packages and emits a new, uniquely named full/medium/small artwork set.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from typing import Callable
import zipfile


VERSION = "1.0"
PREFIX = "UI_SKL_"
DONOR_BASE = "UI_SKL_HPCUREUP_03"
EXPECTED_DONOR_SHA256 = {
    "UI_SKL_HPCUREUP_03_SF.upk": "9348dc79f0aa8897e0532a3d1d9e6ad149485785d7a862197075a314c0abc013",
    "UI_SKL_HPCUREUP_03_M_SF.upk": "ebfb0fa9f158b32d2e619ff87acf607b0dd43527af86595668950f3eee8aaafb",
    "UI_SKL_HPCUREUP_03_S_SF.upk": "d09ef59c69845a116e90d3f7231962a57ebf47e5d0dcc7c52f5f2321c41e4469",
}


@dataclass(frozen=True)
class Variant:
    suffix: str
    size: int
    texture_format: str

    @property
    def donor_filename(self) -> str:
        return f"{DONOR_BASE}{self.suffix}_SF.upk"


VARIANTS = (
    Variant("", 512, "DXT5"),
    Variant("_M", 256, "A8R8G8B8"),
    Variant("_S", 128, "A8R8G8B8"),
)


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_identifier(value: str) -> str:
    """Return the portion following UI_SKL_, suitable for a new package stem."""
    value = value.strip().upper()
    if value.startswith(PREFIX):
        value = value[len(PREFIX):]
    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise ValueError("Enter a decal ID, such as YIPPEE_KI_YAY.")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,39}", value):
        raise ValueError("Decal ID must be 2–40 characters using A–Z, 0–9, and underscores, beginning with a letter.")
    if value.endswith(("_SF", "_M", "_S", "_M_SF", "_S_SF")):
        raise ValueError("Do not include size or _SF suffixes; the cooker adds them automatically.")
    return value


def package_stem(identifier: str) -> str:
    return PREFIX + normalize_identifier(identifier)


def output_filenames(identifier: str) -> tuple[str, str, str]:
    stem = package_stem(identifier)
    return tuple(f"{stem}{variant.suffix}_SF.upk" for variant in VARIANTS)


def read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("The selected artwork is not a valid PNG file.")
    width, height = struct.unpack(">II", header[16:24])
    if not (1 <= width <= 16384 and 1 <= height <= 16384):
        raise ValueError(f"Unsupported PNG dimensions: {width}×{height}.")
    return width, height


def read_dds_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:4] != b"DDS ":
        raise ValueError(f"Cooker produced an invalid DDS file: {path.name}")
    height, width = struct.unpack_from("<II", header, 12)
    return width, height


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if os.name == "nt":
        try:
            import winreg
            for hive, key_name in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(hive, key_name) as key:
                        value, _ = winreg.QueryValueEx(key, "SteamPath" if hive == winreg.HKEY_CURRENT_USER else "InstallPath")
                        roots.append(Path(value))
                except OSError:
                    pass
        except ImportError:
            pass
    roots.extend((
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(r"D:\SteamLibrary"),
        Path(r"E:\SteamLibrary"),
    ))
    return roots


def detect_game() -> Path | None:
    candidates: list[Path] = []
    for steam in _steam_roots():
        candidates.append(steam / "steamapps" / "common" / "LET IT DIE")
        library_file = steam / "steamapps" / "libraryfolders.vdf"
        try:
            text = library_file.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                library = Path(match.group(1).replace(r"\\", "\\"))
                candidates.append(library / "steamapps" / "common" / "LET IT DIE")
        except OSError:
            pass
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            return validate_game(candidate)
        except (OSError, ValueError):
            pass
    return None


def validate_game(game: Path) -> Path:
    game = game.expanduser().resolve()
    cooked = game / "BrgGame" / "CookedPCConsole"
    missing = [variant.donor_filename for variant in VARIANTS if not (cooked / variant.donor_filename).is_file()]
    if missing:
        raise ValueError(
            "That is not a compatible LET IT DIE folder. Missing stock donor package(s): "
            + ", ".join(missing)
        )
    changed = [
        variant.donor_filename
        for variant in VARIANTS
        if sha256_file(cooked / variant.donor_filename) != EXPECTED_DONOR_SHA256[variant.donor_filename]
    ]
    if changed:
        raise ValueError(
            "The stock decal donors do not match the supported offline build: "
            + ", ".join(changed)
            + ". Verify the game files or choose the correct LET IT DIE installation."
        )
    return game


def validate_tool() -> Path:
    tool = resource_root() / "tools" / "UpkTool.exe"
    dependencies = (
        resource_root() / "tools" / "lib64" / "lzo2_64.dll",
        resource_root() / "tools" / "lib64" / "msvcr100.dll",
    )
    missing = [path.name for path in (tool, *dependencies) if not path.is_file()]
    if missing:
        raise ValueError("The cooker bundle is incomplete. Missing: " + ", ".join(missing))
    return tool


def _run_tool(tool: Path, arguments: list[object], log: Callable[[str], None]) -> str:
    display = " ".join(str(value) for value in arguments)
    log(f"> {arguments[0]} {display.split(' ', 1)[1] if ' ' in display else ''}".rstrip())
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run(
        [str(tool), *(str(value) for value in arguments)],
        cwd=tool.parent,
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=flags,
    )
    output = (completed.stdout + completed.stderr).strip()
    if output:
        log(output)
    if completed.returncode:
        raise RuntimeError(f"Artwork tool failed during {arguments[0]} (exit {completed.returncode}).")
    return output


def _unique_output(parent: Path, identifier: str) -> Path:
    base = parent / f"LET-IT-DIE-Decal-{identifier}-Cooked"
    if not base.exists():
        return base
    counter = 2
    while (parent / f"{base.name}-{counter}").exists():
        counter += 1
    return parent / f"{base.name}-{counter}"


def cook_decal(
    source: Path,
    identifier: str,
    game: Path,
    output_parent: Path,
    log: Callable[[str], None] = print,
) -> Path:
    """Cook and validate a three-package decal artwork set.

    Returns the newly created output directory. Existing files and game files
    are never replaced.
    """
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError("Select an existing PNG artwork file.")
    if source.suffix.lower() != ".png":
        raise ValueError("Artwork must be a PNG file.")
    source_dimensions = read_png_dimensions(source)
    identifier = normalize_identifier(identifier)
    stem = PREFIX + identifier
    game = validate_game(game)
    cooked = game / "BrgGame" / "CookedPCConsole"
    tool = validate_tool()
    output_parent = output_parent.expanduser().resolve()
    output_parent.mkdir(parents=True, exist_ok=True)

    collisions = [name for name in output_filenames(identifier) if (cooked / name).exists()]
    if collisions:
        raise ValueError(
            "This decal ID would collide with existing game package(s): "
            + ", ".join(collisions)
            + ". Choose a unique ID."
        )

    final = _unique_output(output_parent, identifier)
    stage = Path(tempfile.mkdtemp(prefix=f".{identifier}-cooking-", dir=output_parent))
    tool_log: list[str] = []

    def record(message: str) -> None:
        message = str(message)
        tool_log.append(message)
        log(message)

    try:
        packages = stage / "packages"
        qa = stage / "validation"
        packages.mkdir()
        qa.mkdir()
        source_hash = sha256_file(source)
        records = []
        record(f"Source: {source.name} ({source_dimensions[0]}×{source_dimensions[1]})")
        record(f"Package stem: {stem}")
        record("The game directory is read-only for this operation.")

        for index, variant in enumerate(VARIANTS, start=1):
            target_stem = stem + variant.suffix
            donor_stem = DONOR_BASE + variant.suffix
            donor = cooked / variant.donor_filename
            dds = qa / f"{target_stem}.dds"
            package = packages / f"{target_stem}_SF.upk"
            extracted = qa / f"extracted-{index}"
            extracted.mkdir()
            record(f"[{index}/3] Creating {package.name}: {variant.size}×{variant.size} {variant.texture_format}")
            _run_tool(tool, ["png2ddsrect", source, dds, variant.size, variant.size, variant.texture_format], record)
            if read_dds_dimensions(dds) != (variant.size, variant.size):
                raise RuntimeError(f"DDS dimension validation failed for {package.name}.")
            _run_tool(tool, ["cook", donor, dds, donor_stem, target_stem, package], record)
            _run_tool(tool, ["validatecooked", package, stem], record)
            _run_tool(tool, ["extract", package, extracted], record)
            extracted_dds = list(extracted.glob("*.dds"))
            if len(extracted_dds) != 1 or read_dds_dimensions(extracted_dds[0]) != (variant.size, variant.size):
                raise RuntimeError(f"Decoded-package validation failed for {package.name}.")
            records.append({
                "file": package.name,
                "size": package.stat().st_size,
                "sha256": sha256_file(package),
                "dimensions": [variant.size, variant.size],
                "format": variant.texture_format,
                "texture_export": f"TX_UI_Image_SKL_{identifier}{variant.suffix}",
                "donor": donor.name,
                "donor_sha256": sha256_file(donor),
                "native_lzo_validated": True,
            })

        manifest = {
            "tool": "LET IT DIE Decal Artwork Cooker",
            "tool_version": VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "decal_id": identifier,
            "package_stem": stem,
            "source_filename": source.name,
            "source_dimensions": list(source_dimensions),
            "source_sha256": source_hash,
            "files": records,
            "game_files_modified": False,
            "artwork_only": True,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        readme = f"""LET IT DIE cooked decal artwork: {identifier}

Created with LET IT DIE Decal Artwork Cooker v{VERSION}.

CONTENTS
- {records[0]['file']} — 512x512 DXT5
- {records[1]['file']} — 256x256 A8R8G8B8
- {records[2]['file']} — 128x128 A8R8G8B8

ARTWORK ONLY
These packages contain the decal images. They do not add a decal record,
gameplay effects, Mushroom Club pool entry, quest, or save ownership.

SAFETY
The cooker only read stock donor packages. It did not modify the game folder.
Do not rename these UPKs after cooking: their internal package/export names
must remain paired with their filenames. Do not overwrite a stock UPK.

See manifest.json for SHA-256 hashes and validation details.
"""
        (stage / "README.txt").write_text(readme, encoding="utf-8")
        (stage / "tool-log.txt").write_text("\n".join(tool_log) + "\n", encoding="utf-8")
        shutil.rmtree(qa)

        archive = stage / f"LET-IT-DIE-Decal-{identifier}-Artwork.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for package in sorted(packages.glob("*.upk")):
                bundle.write(package, "packages/" + package.name)
            bundle.write(stage / "manifest.json", "manifest.json")
            bundle.write(stage / "README.txt", "README.txt")
        with zipfile.ZipFile(archive) as bundle:
            broken = bundle.testzip()
            if broken:
                raise RuntimeError(f"ZIP validation failed at {broken}.")

        stage.rename(final)
        log(f"Complete: {final}")
        return final
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
