"""Create verified standalone and source bundles after PyInstaller build."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "release"
VERSION = "1.0"
BASE = f"LetItDieDecalArtworkCooker-v{VERSION}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_zip(target: Path, root_name: str, files: dict[str, Path]) -> None:
    if target.exists():
        raise RuntimeError(f"Existing release preserved: {target}")
    hashes = {name: sha256(path) for name, path in files.items()}
    with tempfile.TemporaryDirectory(prefix="decal-cooker-package-", dir=ROOT) as temporary:
        staged = Path(temporary) / target.name
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
            for name, path in sorted(files.items()):
                bundle.write(path, f"{root_name}/{name}")
            sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items()))
            bundle.writestr(f"{root_name}/SHA256SUMS.txt", sums)
        with zipfile.ZipFile(staged) as bundle:
            if bundle.testzip():
                raise RuntimeError("ZIP CRC validation failed.")
            bundle.extractall(Path(temporary) / "extracted")
        extracted = Path(temporary) / "extracted" / root_name
        for name, digest in hashes.items():
            if sha256(extracted / name) != digest:
                raise RuntimeError(f"Extracted hash validation failed: {name}")
        shutil.copy2(staged, target)


def main() -> None:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    executable = ROOT / "dist" / f"{BASE}.exe"
    if not executable.is_file():
        raise RuntimeError(f"Build the PyInstaller EXE first: {executable}")

    standalone_exe = OUTPUTS / executable.name
    if standalone_exe.exists():
        raise RuntimeError(f"Existing release preserved: {standalone_exe}")
    shutil.copy2(executable, standalone_exe)

    binary_files = {
        executable.name: executable,
        "README.md": ROOT / "README.md",
        "THIRD-PARTY-NOTICES.txt": ROOT / "THIRD-PARTY-NOTICES.txt",
    }
    binary_zip = OUTPUTS / f"{BASE}.zip"
    write_zip(binary_zip, BASE, binary_files)

    source_files = {
        "cooker_core.py": ROOT / "cooker_core.py",
        "decal_cooker_gui.py": ROOT / "decal_cooker_gui.py",
        "Launch-Source.cmd": ROOT / "Launch-Source.cmd",
        "README.md": ROOT / "README.md",
        "THIRD-PARTY-NOTICES.txt": ROOT / "THIRD-PARTY-NOTICES.txt",
        "tools/UpkTool.exe": ROOT / "tools" / "UpkTool.exe",
        "tools/lib64/lzo2_64.dll": ROOT / "tools" / "lib64" / "lzo2_64.dll",
        "tools/lib64/msvcr100.dll": ROOT / "tools" / "lib64" / "msvcr100.dll",
    }
    source_zip = OUTPUTS / f"{BASE}-Source.zip"
    write_zip(source_zip, f"{BASE}-Source", source_files)

    report = {
        "name": "LET IT DIE Decal Artwork Cooker",
        "version": VERSION,
        "standalone_exe": {
            "path": str(standalone_exe),
            "size": standalone_exe.stat().st_size,
            "sha256": sha256(standalone_exe),
        },
        "binary_zip": {
            "path": str(binary_zip),
            "size": binary_zip.stat().st_size,
            "sha256": sha256(binary_zip),
        },
        "source_zip": {
            "path": str(source_zip),
            "size": source_zip.stat().st_size,
            "sha256": sha256(source_zip),
            "note": "Readable Python GUI source; includes the required compiled UPK helper and DLLs.",
        },
        "game_files_bundled": False,
        "game_writes": False,
        "sizes_generated": [512, 256, 128],
    }
    report_path = OUTPUTS / f"{BASE}-manifest.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
