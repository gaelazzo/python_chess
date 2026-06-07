# Changelog

Tutte le modifiche degne di nota a **Hires Chess Trainer**.
Formato ispirato a [Keep a Changelog](https://keepachangelog.com/);
versionamento [semantico](https://semver.org/lang/it/).

## [1.1.0] - 2026-06-07

### Aggiunte
- **Analisi → cancella variante / tronca**: **Backspace** elimina la variante
  corrente (mossa corrente + seguito), **Canc** tronca le mosse dopo la
  posizione corrente; entrambi con conferma.
- **Salvataggio**: dall'analisi puoi **creare un nuovo file PGN** (non solo
  aggiungere a uno esistente) — comodo per nuovi file di apertura.

### Correzioni
- **Valutazione del motore** (pannello live) ora dal **punto di vista del
  Bianco** (assoluta): la variante migliore ha il valore più alto col Bianco al
  tratto e il più basso col Nero — simmetrica.
- **Orientamento scacchiera in analisi**: il blocco (tasto A) viene ora
  rispettato anche dopo Notazione (V), Load (L) e Setup posizione (U).
- **Caricamento partite**: l'elenco interno rispetta la cartella scelta
  (openings/, endgames/), non più solo pgn/.
- Tutto il codice (UI, messaggi, commenti, docstring) tradotto in inglese.

[1.1.0]: https://github.com/gaelazzo/python_chess/releases/tag/v1.1.0

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
