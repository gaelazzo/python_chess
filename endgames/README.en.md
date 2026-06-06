# `endgames/` — Endgame studies

🇮🇹 *Versione italiana:* [README.md](README.md)

Folder dedicated to **endgame study PGNs** for the *Train endgames* mode
(Main menu → Train endgames → Choose endgame PGN).

## What it contains

`.pgn` files where **each "game" is a single study**:

- The `[SetUp "1"]` + `[FEN "..."]` headers define the starting position of
  the endgame.
- The PGN mainline is **ignored** by the trainer: the judge is the Syzygy
  tablebase (for positions ≤ 7 pieces) with a Stockfish fallback.
- The `[White]` / `[Black]` / `[Event]` metadata can be used as a title
  (e.g. `[White "Lucena"]`, `[Event "K+R vs K — opposition"]`).

## Example game

```pgn
[Event "Lucena position"]
[White "Bridge technique"]
[Black "Drawn?"]
[Result "*"]
[SetUp "1"]
[FEN "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"]

*
```

## How it gets populated

- **Create a new PGN** in a text editor, or
- use the **position editor** in Analysis (key **U**) to build the position
  visually, then **S** to save and pick the `endgames/<name>.pgn` file as
  destination, or
- **export from ChessBase** or another tool able to serialize to PGN with
  FEN headers.

## What happens during training

1. The program picks a random "game" (= study) from the file.
2. Its FEN becomes the starting position of the exercise.
3. You look for the best move; the TB / engine tells you whether it is
   optimal or wrong.
4. **Mistakes** are saved to a learning base `endgames_<filename>` in
   `data/`, drillable from *Solve positions*.

## Typical content example

```
endgames/
├── esempi.pgn                 # mixed basic studies
├── finalitorre.pgn            # rook endgames only
├── KBN_vs_K.pgn               # specific technique drill
└── DEMbase_export.pgn         # export from the Dvoretsky Endgame Manual
```

> **Note**: `.pgn` files are in `.gitignore`. This README gets committed.
