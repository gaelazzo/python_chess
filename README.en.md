# Hires Chess Trainer — User Manual

🇮🇹 *Versione italiana:* [readme.md](readme.md)

**Hires Chess Trainer** is a desktop application for practising and improving at chess.
You can play against the computer or another human, **analyse** games with variations
and annotations, and **study** positions and mistakes through "learning bases" and
lessons (optionally assisted by the *BrainMaster* AI service).

---

## Contents
➡️ **New here?** Start with [Getting started: step-by-step recipes](#getting-started-step-by-step-recipes).

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

Or from **VS Code**: open the folder and press **F5** (the "Avvia Chess" launch config is included in `.vscode/launch.json` with the correct cwd).

For full functionality you'll want (configurable via **Tools → Setup**, see §8):
- a **UCI engine** (e.g. Stockfish) in the `engines/` folder — used for analysis and for playing against the computer;
- (optional) a **Polyglot opening book** (`.bin`) in the `books/` folder;
- (optional) the **BrainMaster** service URL (`base_url`) and your `student id`, if you want to use the assisted lessons.

On startup the **main menu** appears; navigate with the **mouse** or the arrow keys and confirm with **Enter**.

---

## Getting started: step-by-step recipes

*If this is your first time, start here: these are the most common tasks, step by step.*

### Recipe 0 — First-time setup (once)
1. **Tools → Setup → Choose engine**: select the UCI engine (e.g. `stockfish.exe`) from the
   `engines/` folder. Without an engine, analysis and playing against the computer won't work.
2. *(Optional)* **Choose book**: select a `.bin` opening book from `books/`.
3. *(Optional, for lessons)* fill in **base_url** and **student id** for the BrainMaster service.

### Main recipe — *Improve from your games* (wizard)
*The fastest way to train on your own mistakes from Chess.com games:
the wizard automates the steps that Recipes A/B do by hand.*
1. Main menu → **Migliora dalle tue partite** ("Improve from your games").
2. Fill in:
   - **Chess.com user**: your username;
   - **Games**: *White*, *Black* or *Both* (filters the download by colour);
   - **Games (count)**: *Last 500 / 1000 / 2000 / All* (only the monthly archives needed are
     fetched, newest first — useful if you have thousands of games);
   - **Focus**: *Tactics*, *Openings* or *Both* (different parameter presets under the hood);
   - **Accuracy**: *Quick / Balanced / Thorough* (engine time vs depth).
3. **Start** — a progress screen shows `N/M` while the engine analyses. At the end you get
   **Train tactics / openings** buttons that jump straight into *Solve positions* on the
   newly-created base.
4. Later sessions resume from Main menu → **Solve positions** by picking the base
   `<user>_tactics` or `<user>_openings` (persisted in `data/`).

> The wizard is **idempotent**: re-running it after playing more games adds only the new
> mistakes (deduped by zobrist position).

### Recipe A — Correcting your own mistakes (manual flow, as White or Black)
*Goal: review the positions where you went wrong in your own games.*
1. **Download your games** — Tools → Download Chess.com games:
   - *PGN file to create*: a name, e.g. `my_white`;
   - *player*: your Chess.com username;
   - *Player color*: **White** for your White mistakes (use **Black** for Black ones);
   - **Download games**.
2. **Create an empty learning base** — Tools → Create learning base:
   - *filename*: e.g. `white_errors`;
   - *blunderValue*: mistake threshold in centipawns (e.g. `80` ≈ 0.8 pawns worse than the best move);
   - *movesToAnalyze*, *ponderTime*: how many moves to analyse and how much time to give the engine;
   - **Create learning base**.
3. **Fill the base with your mistakes** — Tools → Update learning base:
   - *player*: your username; *Choose PGN file*: `my_white`; *Choose base file*: `white_errors`;
   - **Update Learning Base** (the engine analyses your moves and records the wrong positions).
4. **Review** — Main menu → Solve positions → *Choose base file*: `white_errors` → **Play**.
   Those positions are served back to you: play the right move (**H** reveals the solution).
5. Repeat with **Player color = Black** for your Black mistakes (in a separate base, e.g. `black_errors`).

### Recipe B — Studying an opening / creating "models"
*Goal: train an opening repertoire.*
- **Get the opening PGN**, in two ways:
  - (a) copy an existing `.pgn` file (with the opening lines) into the `pgn/` folder; **or**
  - (b) **build it yourself**: *Play between humans*, play the opening moves, add **variations**
    (play alternative moves with the mouse), optionally annotate (**N**) and comment (**T**),
    then **Save (S)** to a PGN file.
- **Train on the repertoire** — Main menu → Study openings → *Choose PGN file* (your PGN)
  + *You play* (White/Black) → **Play**: the computer plays the stored lines and you must find
  the right move.
- **(Alternatively) turn it into a study base** — Tools → Create learning base (e.g. `opening_x`)
  → Tools → **Unroll PGN file** (*Choose PGN* + *You play* your colour + *Choose base*) → then
  review it with **Solve positions**.

### Recipe C — Analysing a game with variations and annotations
1. Main menu → **Play between humans**.
2. Load a game (**L**) or play it; step through with **←/→**.
3. Try alternative moves **with the mouse** → they are added as variations.
4. Annotate the quality (**N**) and add comments (**T**).
5. See it all in the **Notation panel** (**V**); navigate with ←/→ and ↑/↓.
6. **Save (S)** or copy the PGN (**G**) to resume it later.

### Recipe D — Spaced-repetition lessons (BrainMaster)
*(Requires `base_url` configured in Setup.)*
1. Create a learning base (Recipe A or B).
2. Tools → **Create Course for BrainMaster** → *Choose base file* → **Create** (registers the
   base as a course). *(Alternatively: Tools → Unroll PGN file as lesson.)*
3. Main menu → **BrainMaster lessons** → choose the course → **Exercise**: the service decides
   which positions to serve you and when.

---

## 2. The main menu

| Item | What it does |
|------|--------------|
| **Migliora dalle tue partite** | Guided wizard: download your Chess.com games → find mistakes (tactics/openings) → jump straight into local practice. The fastest way to train on your own mistakes (see §3.1). |
| **Play against computer** | Play a game against the engine. |
| **Play between humans** | Two human players on the same board. This is also the **analysis mode** (where you can add variations and annotations). |
| **Solve positions** | Review the positions (mistakes) stored in a *learning base*. |
| **BrainMaster lessons** | Lessons driven by the BrainMaster service *(shown only if `base_url` is configured)*. |
| **Study openings** | Practise on "model" games: you must find the best move yourself. |
| **Tools** | Create/update learning bases, import PGN/Chess.com games, Setup. |
| **Quit** | Exit the program (also with **`Q`** or by closing the window). |

---

## 3. The modes

### 3.1 Improve from your games (wizard)
> **Guided path.** From minimal input (Chess.com username + 4 selectors) the wizard does
> everything: downloads games, creates/updates learning bases, analyses them with
> auto-chosen presets, and drops you straight into local practice.

Parameters:
- **Chess.com user** — your username.
- **Games** — *White* / *Black* / *Both* (filters the download).
- **Games (count)** — *Last 500 / 1000 / 2000 / All*. Only the monthly archives needed are
  fetched, newest first; designed for players with tens of thousands of games (e.g. bullet/blitz)
  who don't want to revisit ancient mistakes.
- **Focus** — *Tactics*, *Openings* or *Both*. These are **two distinct analyses** with
  different parameters under the hood: tactics scans the whole game with a high blunder
  threshold (only real blunders); openings looks at the first moves with `useBook=True`,
  so book moves are never flagged and you find the deviations that worsen the evaluation.
  Picking *Both* runs the engine **twice** over the same games (one pass per focus).
- **Accuracy** — *Quick / Balanced / Thorough*: presets for `ponderTime`, `blunderValue`,
  `movesToAnalyze`, tuned per focus.

When the analysis ends you get **Train tactics / openings** buttons that drop you into
*Solve positions* on the `<user>_tactics` or `<user>_openings` base (see §3.4). The bases
persist in `data/`; later sessions resume directly from *Solve positions* by picking the base.

### 3.2 Play against computer
Set the parameters and press **Play**:
- **You play**: White / Black / Random (which side you take);
- **ELO**: engine strength (1350–2850);
- **ELO MAX**: if on, the engine plays at full strength, ignoring the ELO setting.

Move with the mouse; the computer replies automatically.

### 3.3 Play between humans (analysis)
Two humans move in turn on the same board. Since **there is no engine replying**,
this is the right mode to **analyse**: you can take moves back, try alternative moves
(variations), annotate and comment them (see §5 and §6).

### 3.4 Solve positions
> **One position, one move.** You're given a position and must play the right move.
> Good for reviewing *anything* (mistakes, tactics, endgames…).

Review the positions stored in a *learning base* (typically your own mistakes).
Parameters:
- **ECO (optional)**: filter by opening code;
- **Choose base file**: pick the learning base;
- **Lead-in moves**:
  - *Skip* (default) — skips the lead-in move sequence and drops you straight onto the
    mistake-position to solve;
  - *Replay* — the program **replays the original game's move sequence** up to the
    position, so you "step into" the context before answering (especially useful for
    openings).
- **Num Moves to Show**: number of **continuation** moves the program plays *after* you
  answer correctly, to show how the game should proceed with correct play. `0` = no
  continuation.
- **Practice order**:
  - *Random* (default) — plain `random.shuffle`, positions come up in random order. Default
    because on real bases (especially openings) priority tends to saturate the session on a
    few positions with very high `wrong` (e.g. the first moves of an opening repeated dozens
    of times across your games).
  - *Priority* — sorts by priority `(times you got the position wrong, severity)`: the most
    recurring and most severe come first. "Drill" mode — useful when you want to force the
    closure of the worst positions, accepting that the session focuses on them.

A position is shown: **play the move you think is correct**. The program tells you
whether it's right; press **H** to reveal the solution.

> **Review session.** *Solve positions* keeps a "live" session with at most
> `maxErrorsToConsider` active positions (default 10, configurable in **Setup**). A position
> enters when proposed; it leaves **immediately** if you solve it on the first try, otherwise
> after `correctsToLearn` consecutive correct answers (default 3, configurable in Setup) once
> you've missed it. Fully learned positions (`serie ≥ 5` over the whole history, not just the
> current session) are **excluded from the base for life**.

### 3.5 BrainMaster lessons
Same idea, but the positions and review order are suggested by the **BrainMaster**
service (spaced repetition). Choose the **course** and press **Exercise**.
*(Visible only if `base_url` is configured in Setup.)*

### 3.6 Study openings
> **A whole line.** You play the entire sequence from your side (your moves are fixed),
> while the computer may reply with **different variations** among the stored ones.
> Typical for **drilling openings** / a repertoire.

You load a PGN file of "model" lines. The computer plays one of the stored lines and
**you must find the best move** at each turn.
- **You play**: White / Black;
- **Choose PGN file**: the file with the model lines;
- **Lead-in moves** and **Num Moves to Show**: same semantics as *Solve positions*
  (§3.4) — *Skip* skips the lead-in and starts at the position, *Replay* replays it;
  *Num Moves to Show* is the number of continuation moves shown after a correct answer.

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

> In the study modes (Solve positions / BrainMaster / Study openings) the controls
> are similar but solution-oriented: **Q** quit, **C/G** copy, **E/B/D** panels,
> **+** show a few more moves (hint), **H** reveal the solution.

> **End of game.** On checkmate / stalemate the result message stays on screen and the
> view **does not auto-close**: you can still **save (S)**, **take back the last move (←)**,
> **reset (R)** or quit (**Q**) whenever you want.

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

Press **`V`** (in Play between humans) to open a panel **alongside the board** showing the
**whole game**: main line and **tree-indented variations**, with glyphs and comments. The
board stays visible on the left and **updates live** to follow the selected move in the
panel (no more corner mini-board — the real board acts as the preview).

| Control | Action |
|---------|--------|
| **←** / **→** | Previous / next move |
| **↑** / **↓** | Previous / next line (move between main line and variations) |
| **wheel**, **PgUp/PgDn**, **Home/End** | Scroll the view |
| **click on a move** | Jump to that position (closes the panel) |
| **V** / **Esc** | Close the panel |

On closing, the main board stays on the selected move. While the panel is open the board
is not clickable for piece moves: you navigate from the panel.

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
| **Setup** | Configure (persisted in `config.json`): `base_url` and `student id` (BrainMaster), **Choose engine** (UCI engine), **Choose book** (opening book), **Max errors in session** (capacity of the *Solve positions* session, default 10) and **Corrects to learn** (consecutive corrects needed to leave the session after a mistake, default 3). |

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
| `severity` | `int` | Worst eval drop (cp) observed for this mistake — used to prioritise in *Solve positions*. Populated by analysis (`analyzeGame`) as `prevScore - evaluation`; on repeated encounters the max wins. Defaults to `0` for bases loaded from a CSV without the column (backward-compatible). |

`LearnPosition` also offers PGN conversion methods (`to_Pgn`, `to_PgnString`) and a
`from_dict` constructor (used to read CSV rows).

### Learning logic

When the user plays a move, `updatePositionStats` updates the position:
- increments `ntry` and updates `firstTry`/`lastTry`;
- if the move matches `ok`, increments `successful` and the success `serie`; after
  **5 consecutive successes** (`serie >= 5`) the position is marked as learned (`skip = True`)
  and excluded **for life** from the base;
- if the move is wrong, `serie` becomes negative (resetting any positive streak).

Separately, within a **session of *Solve positions*** there is a second countdown: a
mistake-position leaves **the current session** only after `config.correctsToLearn`
consecutive correct answers (default 3, configurable in Setup). The session holds at most
`config.maxErrorsToConsider` active positions (default 10). The two thresholds are
independent: `correctsToLearn` rules leaving the **session**, `serie >= 5` rules permanent
exclusion from the base.

### Priority in *Solve positions*

`analyzer.getPositions(learningBase, filter, order)` returns the not-yet-learned positions
ordered by `order`:
- `"priority"` — `random.shuffle` (tiebreak) + stable `sort` by
  `(ntry - successful, severity)`. The highest priority ends up at the tail of the list and
  the consumer in `solvePositionsFromBase` serves it first via `pop()`. Effective only if
  `ntry` / `successful` / `severity` differ across positions (see §3.4).
- `"random"` — plain `random.shuffle`, no sorting.

The mode is picked in the *Solve positions* menu (*Practice order* selector).

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
| `notation.py` | Notation panel (tree view next to the board) |
| `move_speech.py` | Expands SAN moves in TTS-read comments (`Qe4` → "Queen to e4") |
| `modes/` | The game modes: `play_game`, `brainmaster`, `replay`, `improve` (wizard), `openings` (+ `common`) |
| `GameState.py` | Game state, PGN tree, moves, annotations |
| `BoardScreen.py` | Board and panel rendering |
| `UCIEngines.py`, `book.py` | UCI engine and opening book |

Tests are in `tests/` (run with `python -m pytest`).
