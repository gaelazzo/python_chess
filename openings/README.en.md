# `openings/` — Opening repertoire

🇮🇹 *Versione italiana:* [README.md](README.md)

Folder dedicated to **opening repertoire PGNs** for the *Study openings*
mode (Main menu → Study openings → Choose opening PGN).

## What it contains

`.pgn` files structured as **variation trees**, NOT as real games:

- Each file typically represents ONE opening (e.g. `C42Russian.pgn`,
  `c96.pgn`) or a sub-system of an opening.
- Your moves (of the side you play) make up the mainline.
- The opponent's moves are encoded as PGN **variations** — the app
  navigates them as random alternatives.
- No `[FEN]` header: you always start from the standard initial position.

## Example game / line

```pgn
[Event "C42 Russian — White's repertoire"]
[White "Repertoire White"]
[Black "Repertoire Black"]
[Result "*"]

1. e4 e5 2. Nf3 Nf6 (2... Nc6 3. Bb5) 3. Nxe5 (3. d4 *) d6 4. Nf3 Nxe4
5. d4 d5 *
```

In Study openings: you play White, your mainline moves (1.e4, 2.Nf3,
3.Nxe5...) are "constrained" — you must guess them. Black's moves are
variations from the PGN's point of view: the program picks at random among
the stored alternatives (2...Nf6 vs 2...Nc6, etc.).

## Color auto-detect

The app counts all the variations in the file and takes the majority:
- `(N... move)` variations = Black's alternatives → user plays **White**.
- `(N. move)` variations = White's alternatives → user plays **Black**.
- Tie or no variations → default White.

## How it gets populated

- **Build one yourself** as a PGN in the Analysis editor: start from a
  position, enter your moves, add the opponent's variations with the mouse,
  then **S** to save to `openings/<name>.pgn`.
- **Copy an existing PGN** (opening books, online databases) and drop it
  here.
- **Export from ChessBase** or similar tools from the "opening" sections of
  your catalogue.

## What happens during training

1. The program draws a random line from the PGN (Lead-in = Skip or Replay,
   see main readme §3.6).
2. You find the right move on each turn; the program replies with one of
   the opponent's alternatives.
3. **Mistakes** are saved to `openings_<filename>` in `data/`, drillable
   from *Solve positions*.

## Typical content example

```
openings/
├── C42Russian.pgn             # Russian defence for Black
├── c96.pgn                    # Spanish closed variation
├── CaroKan.pgn                # your Caro-Kann line
└── KingsIndian.pgn            # King's Indian opening for White
```

> **Note**: `.pgn` files are in `.gitignore`. This README gets committed.
