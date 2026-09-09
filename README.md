# LET IT DIE Decal Artwork Cooker

A Windows GUI that turns one PNG into the complete three-package artwork set used by a *LET IT DIE* skill decal:

- `UI_SKL_YOUR_ID_SF.upk` — 512×512, DXT5
- `UI_SKL_YOUR_ID_M_SF.upk` — 256×256, A8R8G8B8
- `UI_SKL_YOUR_ID_S_SF.upk` — 128×128, A8R8G8B8

Every generated package is reopened and validated. The cooker also creates a ready-to-share ZIP, a manifest containing dimensions and SHA-256 hashes, and a text log.

## Important limits

This creates artwork packages only. It does **not** add a database decal record, gameplay effect, Mushroom Club pool entry, quest, or save ownership. It does not install or overwrite files in the game.

The cooker reads three stock donor packages from the user's own installation. Those game packages are not included in this repository or its releases.

## GUI use

1. Close programs that are editing the source PNG.
2. Run `LetItDieDecalArtworkCooker-v1.0.exe` from the Releases page, or use the source launcher described below.
3. Select a square PNG (at least 128×128).
4. Enter a unique ID such as `YIPPEE_KI_YAY`. The `UI_SKL_` prefix and size suffixes are automatic.
5. Confirm or browse to the *LET IT DIE* installation folder.
6. Choose an output parent folder.
7. Click **Cook and validate all 3 sizes**.

The tool refuses IDs that would collide with packages already present in the game. Do not rename the output UPKs because their internal names must match their filenames.

## Run from source

Requirements:

- Windows
- Python 3.11 or newer with `tkinter`

Clone or download the complete repository and run `Launch-Source.cmd`. Keep `cooker_core.py`, `decal_cooker_gui.py`, and `tools/` together.

The source version also supports a command line:

```bat
py -3 decal_cooker_gui.py --image "art.png" --id "MY_DECAL" ^
  --game "D:\SteamLibrary\steamapps\common\LET IT DIE" ^
  --output "C:\My Cooked Decals"
```

## Build the standalone EXE

Install PyInstaller, then run:

```bat
py -3 -m PyInstaller --clean LetItDieDecalArtworkCooker-v1.0.spec
```

The executable is created under `dist/`. Run the tests before publishing a build:

```bat
py -3 -m unittest -v test_cooker.py
```

Set `LID_GAME_DIR` and `LID_TEST_PNG` to enable the optional real-package integration test.

## Safety and sharing

- Existing output folders are preserved; repeated cooks create a numbered folder.
- Stock game packages are read-only and are never overwritten.
- Only use and distribute artwork you have permission to use.
- This is an unofficial community tool and is not affiliated with GungHo, Supertrick Games, Epic Games, or Valve.

The bundled helper is based on UPKManager components. See [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).

