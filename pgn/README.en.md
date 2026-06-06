# `pgn/` — Your games

🇮🇹 *Versione italiana:* [README.md](README.md)

Default folder for "generic" `.pgn` files: **your downloaded games** or
**analysed / annotated games**. Used by several modes:

- **Improve from your games** (wizard): downloads your Chess.com / lichess
  games here (e.g. `gaelazzo_chesscom.pgn`).
- **Tools → Download Chess.com / Download lichess games**: incremental
  append-only download into the same file (dedup by `[Link]` URL).
- **Tools → Update learning base**: reads from here the PGNs to analyse with
  the engine to find the blunders.
- **Analysis / Human Play**: key **S** saves here (you can browse to another
  folder if you want). Key **L** loads from here to step through / analyse a
  game.
- **Suggestion for study (Study advisor)**: reads a PGN from here for the
  ranking of the ECOs to study.

## What NOT to put here

- **Opening repertoire** → `openings/` folder. These are PGNs with explicit
  variations that Study openings navigates as a tree, not real games.
- **Endgame studies** → `endgames/` folder. These are individual positions
  with a `[FEN]` header, each one an exercise.

## Typical content example

```
pgn/
├── gaelazzo_chesscom.pgn      # incremental Chess.com download
├── gaelazzo_lichess.pgn       # incremental lichess download
├── all.pgn                    # all games (also merged)
├── all.pgn.idx                # position-stats cache (see below)
└── my_analysis.pgn            # manually annotated games
```

The `<pgn>.idx` file (if present) is the binary cache of position
statistics, built by `position_stats.py` the first time you use the DB as a
reference (key **Y** in Analysis). It regenerates automatically if you
modify the PGN. It is in `.gitignore`.

> **Note**: `.pgn` files are in `.gitignore` (your data is private). This
> README gets committed.
