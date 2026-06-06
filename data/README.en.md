# `data/` — Learning bases

🇮🇹 *Versione italiana:* [README.md](README.md)

The **learning bases** folder: positions to study/review together with the
statistics of your attempts. Read automatically at startup (see
`LearningBase.py`) and populated by the training modes.

## What it contains

Each learning base is made of **two files**:

| File | Content |
|------|---------|
| `base_<name>.json` | Metadata: `movesToAnalyze`, `blunderValue`, `ponderTime`, `useBook`. |
| `<name>.csv` | One position per row: `zobrist`, `fen`, `ok`, `move`, `moves`, `ntry`, `successful`, `severity`, `serie`, `skip`, etc. |

The app loads everything matching `base_*.json` (the `base_` prefix is
stripped from the name). Bases show up in the dropdowns of *Solve positions*
and *BrainMaster lessons*.

## How they get populated (do NOT edit by hand)

No manual editing of the CSVs — the files are managed by the program:

- **Tools → Create learning base**: creates an empty base.
- **Tools → Update learning base**: the engine analyses a PGN, finds the
  blunders and adds them.
- **Tools → Unroll PGN file**: turns every position of a PGN into an entry
  of the base (handy to drill a complete opening).
- **Improve from your games** (wizard): automatic orchestration of
  download + analysis + creation of `<user>_tactics` and `<user>_openings`.
- **Train endgames / Study openings**: every mistake you make is saved to
  `endgames_<filename>` and `openings_<filename>` respectively.
- **Analysis → key K**: manually save (position + correct move) into a base
  of your choice.

## What it does NOT contain

- PGN files (they go in `pgn/`, `endgames/`, `openings/` depending on use).
- `.idx` files (position-stats cache: they live next to the reference PGN).

## Backup

If something goes wrong, just copy the whole `data/` folder to preserve all
your learning history.

> **Note**: the entire `data/` folder is in `.gitignore` (your data is
> private). This README is whitelisted — it is the only file in `data/` that
> gets committed.
