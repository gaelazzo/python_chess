# Changelog

Tutte le modifiche degne di nota a **Hires Chess Trainer**.
Formato ispirato a [Keep a Changelog](https://keepachangelog.com/);
versionamento [semantico](https://semver.org/lang/it/).

## [1.0.0] - 2026-06-06

Prima release pubblica.

### Modalità principali
- **Improve from your games** — wizard che scarica le tue partite da
  Chess.com, trova gli errori (tattica/aperture) con il motore e li trasforma
  in *learning base* allenabili. Idempotente: rilanciandolo aggiunge solo i
  nuovi errori.
- **Solve positions** — ripasso a **ripetizione spaziata** delle posizioni in
  cui hai sbagliato.
- **Study openings** — allenamento del repertorio d'apertura da PGN ad albero
  di varianti (cartella `openings/`), con auto-rilevamento del colore.
- **Train endgames** — studi di finale giudicati dalle **Syzygy tablebase**
  (≤ 7 pezzi) con fallback Stockfish (cartella `endgames/`).
- **Analysis / Human Play** — analisi con varianti, annotazioni e commenti,
  pannello di notazione, statistiche di posizione contro un PGN di riferimento.
- **Play vs computer** e **Human play**.
- **Suggestion for study** — ranking degli ECO per urgenza di studio.

### Altro
- Import partite da **Chess.com** e **lichess** (download incrementale,
  append-only, dedup per URL).
- Sintesi vocale (TTS) delle mosse; splash screen all'avvio.
- Auto-tracking degli errori in ogni modalità di allenamento.

### Requisiti
- Motore **UCI (Stockfish)** da scaricare a parte; opzionali libro Polyglot e
  Syzygy tablebase. Vedi [INSTALL.md](INSTALL.md).
- Windows-first.

[1.0.0]: https://github.com/gaelazzo/python_chess/releases/tag/v1.0.0
