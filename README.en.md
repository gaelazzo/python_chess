# Hires Chess Trainer — User Manual

🇮🇹 *Versione italiana:* [readme.md](readme.md)

**Hires Chess Trainer** is a desktop application for practising and improving at chess.
You can play against the computer or another human, **analyse** games with variations
and annotations, and **study** positions and mistakes through "learning bases" and
lessons (optionally assisted by the *BrainMaster* AI service).

---

## Contents
1. [Getting started](#1-getting-started)
2. [The main menu](#2-the-main-menu)
3. [The modes](#3-the-modes)
4. [In-game controls](#4-in-game-controls)
5. [Analysing a game: variations, annotations, comments](#5-analysing-a-game)
6. [The Notation panel](#6-the-notation-panel)
7. [Saving and loading games](#7-saving-and-loading-games)
8. [Tools](#8-tools)
9. [Key concepts](#9-key-concepts)
10. [Files and folders](#10-files-and-folders)
11. [Technical appendix](#technical-appendix-learning-base-format)

---

## 1. Getting started

Launch the program with:

```
python chessMain.py
```

For full functionality you'll want (configurable via **Tools → Setup**, see §8):
- a **UCI engine** (e.g. Stockfish) in the `engines/` folder — used for analysis and for playing against the computer;
- (optional) a **Polyglot opening book** (`.bin`) in the `books/` folder;
- (optional) the **BrainMaster** service URL (`base_url`) and your `student id`, if you want to use the assisted lessons.

On startup the **main menu** appears; navigate with the **mouse** or the arrow keys and confirm with **Enter**.

---

## 2. The main menu

| Item | What it does |
|------|--------------|
| **Play against computer** | Play a game against the engine. |
| **Play between humans** | Two human players on the same board. This is also the **analysis mode** (where you can add variations and annotations). |
| **Play a dataset** | Review the positions (mistakes) stored in a *learning base*. |
| **BrainMaster lessons** | Lessons driven by the BrainMaster service *(shown only if `base_url` is configured)*. |
| **Exercise by models** | Practise on "model" games: you must find the best move yourself. |
| **Tools** | Create/update learning bases, import PGN/Chess.com games, Setup. |
| **Quit** | Exit the program (also with **`Q`** or by closing the window). |

---

## 3. The modes

### 3.1 Play against computer
Set the parameters and press **Play**:
- **You play**: White / Black / Random (which side you take);
- **ELO**: engine strength (1350–2850);
- **ELO MAX**: if on, the engine plays at full strength, ignoring the ELO setting.

Move with the mouse; the computer replies automatically.

### 3.2 Play between humans (analysis)
Two humans move in turn on the same board. Since **there is no engine replying**,
this is the right mode to **analyse**: you can take moves back, try alternative moves
(variations), annotate and comment them (see §5 and §6).

### 3.3 Play a dataset
Review the positions stored in a *learning base* (typically your own mistakes).
Parameters:
- **ECO (optional)**: filter by opening code;
- **You play**: White / Black / Any;
- **Choose base file**: pick the learning base;
- **Skip initial moves** / **Num Moves to Show**: how many opening moves to show before asking you to move.

A position is shown: **play the move you think is correct**. The program tells you
whether it's right; press **H** to reveal the solution.

### 3.4 BrainMaster lessons
Same idea, but the positions and review order are suggested by the **BrainMaster**
service (spaced repetition). Choose the **course** and press **Exercise**.
*(Visible only if `base_url` is configured in Setup.)*

### 3.5 Exercise by models
You load a PGN file of "model" games. The computer plays one of the stored lines and
**you must find the best move** at each turn.
- **You play**: White / Black;
- **Choose PGN file**: the file with the model games;
- **Skip initial moves** / **Num Moves to Show**: opening moves to show.

---

## 4. In-game controls

During a game (Play against computer / between humans) the following controls apply.
**Hold the right mouse button** to see the on-screen help.

| Key | Action |
|-----|--------|
| **mouse click** | Click the source square then the destination square to move |
| **right mouse button** (held) | Show the help panel |
| **←** | Take back one move |
| **→** | Go to the next move (if several variations exist, pick from a menu) |
| **C** | Copy the current position (FEN) to the clipboard |
| **G** | Copy the whole game (PGN, with variations and annotations) to the clipboard |
| **S** | Save the game |
| **A** | Analysis mode (locks the board orientation) |
| **F** | Flip the board |
| **R** | Reset (new game) |
| **E** | Analysis engine ON/OFF (shows the evaluation) |
| **B** | Show/hide the opening book |
| **D** | Show/hide the move list |
| **Q** | Back to the main menu |

**Only in "Play between humans" (analysis):**

| Key | Action |
|-----|--------|
| **L** | Load a game (starts from the first move; step through with →) |
| **N** | Annotate the last move with a glyph (`!`, `?`, `!!`, `??`, `!?`, `?!`, `±`, …) |
| **T** | Add a text comment to the last move |
| **V** | Open the **Notation** panel (whole game + variations) |

> In the study modes (Play a dataset / BrainMaster / Exercise by models) the controls
> are similar but solution-oriented: **Q** quit, **C/G** copy, **E/B/D** panels,
> **+** show a few more moves (hint), **H** reveal the solution.

---

## 5. Analysing a game

In **Play between humans** you can build and annotate the analysis of a game.

**Adding variations.** Move to a position (with ←/→), then **play a different move with
the mouse** than the one already there: it is automatically added as a **variation** from
that point. Existing moves are followed with **→** (if there are several continuations a
selection menu appears).

**Annotating move quality (key `N`).** Opens a menu of standard glyphs; the chosen one is
shown next to the move in the list (e.g. `2. Nf3!`). A move has a **single** assessment:
choosing another one replaces the previous; *(remove all)* clears it. Available glyphs:

| Glyph | Meaning | Glyph | Meaning |
|-------|---------|-------|---------|
| `!` | good move | `=` | equal position |
| `?` | mistake | `∞` | unclear |
| `!!` | excellent move | `⩲` / `⩱` | White / Black slightly better |
| `??` | blunder | `±` / `∓` | White / Black better |
| `!?` | interesting | `+−` / `−+` | White / Black winning |
| `?!` | dubious | `□` | only move |

**Commenting a move (key `T`).** Opens a text field: type the comment and press **Save**.
The comment appears in the move list (in yellow) and in the Notation panel.

**Persistence.** Glyphs and comments are stored in the PGN: with **S** (save) or **G**
(copy PGN) they stay in the game and are restored when you reopen it, even in other chess
programs.

---

## 6. The Notation panel

Press **`V`** (in Play between humans) to open a full-screen view of the **whole game**:
the main line and **tree-indented variations**, with glyphs and comments. A **mini board**
in the bottom-right corner shows the selected position.

| Control | Action |
|---------|--------|
| **←** / **→** | Previous / next move |
| **↑** / **↓** | Previous / next line (move between main line and variations) |
| **wheel**, **PgUp/PgDn**, **Home/End** | Scroll the view |
| **click on a move** | Jump to that position (closes the panel) |
| **V** / **Esc** | Close the panel |

As you navigate, the highlighted move and the mini board update; on closing, the main
board stays on the selected move.

---

## 7. Saving and loading games

- **Save** (key **S**): open the Save menu, choose/create the PGN file and the game
  details (players, event, etc.), then **Save**. Games are stored in `pgn/`.
- **Load** (key **L**, only in Play between humans): pick the PGN file and the game from
  the list. The game is loaded **from the start**, so you can step through it with **→**
  and explore its variations.

---

## 8. Tools

| Tool | Purpose |
|------|---------|
| **Download Chess.com games** | Download a player's games from Chess.com into a PGN file (give the file to create, the *player* and the colour). |
| **Create learning base** | Create a new, empty learning base: `movesToAnalyze`, `blunderValue` (mistake threshold in centipawns), `ponderTime`, `useBook`, `filename`. |
| **Update learning base** | Analyse a *player*'s games in a PGN and **record the mistakes** into the chosen base (mistake correction). |
| **Unroll PGN file** | Turn a PGN into a set of **positions** inside a learning base. |
| **Unroll PGN file as lesson** | Same, but as a **lesson** (for review / BrainMaster). |
| **Create Course for BrainMaster** | Register a learning base as a BrainMaster **course** *(if `base_url` is configured)*. |
| **Setup** | Configure: `base_url` and `student id` (BrainMaster), **Choose engine** (UCI engine), **Choose book** (opening book). |

---

## 9. Key concepts

- **Learning base** — a store of positions to study, with the statistics of your attempts.
  See the technical appendix for the format. It typically holds your mistakes (created via
  *Update learning base*) or positions extracted from games (*Unroll PGN*).
- **BrainMaster** — an external (AI) service that proposes positions to review with spaced
  repetition; requires `base_url` and a `student id`.
- **ECO** — the standard code identifying an opening (e.g. `C42`); used for filtering.
- **ELO** — a measure of playing strength; for the computer it is set in *Play against computer*.
- **FEN / PGN** — standard notations: FEN describes a single position, PGN a whole game
  (with variations, glyphs and comments).
- **Glyphs (NAGs)** — the annotation symbols `! ? !? ± …` (see §5).

---

## 10. Files and folders

| Folder | Contents |
|--------|----------|
| `data/` | Learning bases (`base_<name>.json` + `<name>.csv`) |
| `pgn/` | Saved games and imported PGN files |
| `engines/` | UCI engines (e.g. Stockfish) |
| `books/` | Polyglot opening books (`.bin`) |

---

# Technical appendix: Learning Base format

The *Learning Base* is the data structure that stores the positions to study/train and
tracks the user's progress on each of them. It is implemented in
[LearningBase.py](LearningBase.py).

### On-disk layout

Each learning base consists of **two files** stored in the `data/` folder:

| File | Contents |
|------|----------|
| `base_<name>.json` | Base metadata/parameters (serialises `LearningBaseData`) |
| `<name>.csv` | List of positions, one per row (serialises the `LearnPosition`s) |

At startup the module automatically loads every base present: it looks for `base_*.json`
files in `data/`, loads them and exposes them in the `learningBases` dictionary, keyed by
name (the `base_` prefix is removed by `stripBaseName`). If `data/` does not exist it is
created.

### `LearningBase` (the base)

Container class. Holds the dictionary of positions and the analysis parameters.

| Field | Type | Description |
|-------|------|-------------|
| `positions` | `Dict[int, LearnPosition]` | Positions, keyed by Zobrist hash |
| `movesToAnalyze` | `int` | Number of moves to analyse |
| `blunderValue` | `int` | Threshold (centipawns) to consider a move a mistake |
| `ponderTime` | `float` | Engine analysis/ponder time |
| `useBook` | `bool` | Whether to use the opening book |
| `filename` | `Optional[str]` | Base name of the on-disk files |

The metadata (`movesToAnalyze`, `blunderValue`, `ponderTime`, `useBook`, `filename`) is
wrapped in `LearningBaseData` for the JSON file, while the positions are written separately
to the CSV file.

Main methods:
- `load(filename)` / `save(filename)` — load and save (JSON + CSV).
- `addPosition(game, board, goodMove)` — add a new position (if not already present).
- `updatePosition(moveMade, goodMove, game, board)` — analyse the move played by the user
  and update the position's statistics.
- `updatePositionStats(position, moveMade, date)` — statistics update logic; returns `True`
  if the played move is the correct one.

### `LearnPosition` (a single position)

A dataclass representing a study position. Each CSV row corresponds to one `LearnPosition`.

| Field | Type | Description |
|-------|------|-------------|
| `zobrist` | `int` | Zobrist hash of the position (unique key) |
| `fen` | `str` | Position in FEN notation |
| `ok` | `str` | Correct move (UCI) expected in this position |
| `move` | `str` | Move actually played |
| `moves` | `str` | Sequence of UCI moves leading to the position |
| `successful` | `int` | Number of successful attempts |
| `ntry` | `int` | Total number of attempts |
| `white` | `str` | White player (from the source game) |
| `black` | `str` | Black player (from the source game) |
| `eco` | `Optional[str]` | ECO code of the opening |
| `gamedate` | `Optional[date]` | Date of the source game |
| `lastTry` | `Optional[date]` | Date of the last attempt |
| `firstTry` | `Optional[date]` | Date of the first attempt |
| `serie` | `int` | Current streak counter (positive = consecutive successes, negative = mistakes) |
| `skip` | `bool` | Position "learned", to be skipped during review |
| `idquiz` | `Optional[int]` | Associated quiz id (optional) |

`LearnPosition` also offers PGN conversion methods (`to_Pgn`, `to_PgnString`) and a
`from_dict` constructor (used to read CSV rows).

### Learning logic

When the user plays a move, `updatePositionStats` updates the position:
- increments `ntry` and updates `firstTry`/`lastTry`;
- if the move matches `ok`, increments `successful` and the success `serie`; after
  **5 consecutive successes** (`serie >= 5`) the position is marked as learned (`skip = True`);
- if the move is wrong, `serie` becomes negative (resetting any positive streak).

---

## Code architecture (for developers)

The code is organised into single-responsibility modules (a refactoring of `chessMain.py`):

| Module | Role |
|--------|------|
| `chessMain.py` | Orchestrator: builds the menu (`mainMenu`) and runs the loop (`runMain`) |
| `app_context.py` | pygame infrastructure state (screen, manager, fonts, clock…) as the `app` object |
| `state.py` | Shared session state (parameters, constants) |
| `game_loop_common.py` | Helpers shared by the game loops (help overlay, panel toggles, clipboard) |
| `menu_helpers.py` | Menu builders (file selectors, callbacks, etc.) |
| `save_load.py` | Game saving/loading and related menus |
| `learningbase_admin.py` | Learning-base creation/update, PGN/Chess.com import |
| `notation.py` | Notation panel (tree view + mini board) |
| `modes/` | The game modes: `play_game`, `brainmaster`, `replay`, `models` (+ `common`) |
| `GameState.py` | Game state, PGN tree, moves, annotations |
| `BoardScreen.py` | Board and panel rendering |
| `UCIEngines.py`, `book.py` | UCI engine and opening book |

Tests are in `tests/` (run with `python -m pytest`).
