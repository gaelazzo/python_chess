# Changelog

Tutte le modifiche degne di nota a **Hires Chess Trainer**.
Formato ispirato a [Keep a Changelog](https://keepachangelog.com/);
versionamento [semantico](https://semver.org/lang/it/).

## [1.2.3] - 2026-06-10

### Correzioni
- **Modi che richiedono il motore, senza motore configurato**: "Play vs
  computer", "Endgame training" e "Improve from your games" non vanno più in
  crash — mostrano un messaggio chiaro ("Configure an engine first…") e tornano
  al menu. Anche il tasto **E** (motore on/off) avvisa se manca il motore.
- **Messaggi sulla scacchiera tagliati**: i testi più larghi della scacchiera non
  vengono più troncati a sinistra (il font si adatta per stare nello spazio).

[1.2.3]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.3

## [1.2.2] - 2026-06-10

### Correzioni
- **Crash in "Play vs computer"** su un'installazione nuova: un'opzione di
  configurazione mancante (`engine_usebook`) faceva terminare il programma quando
  il motore muoveva. Risolto.
- **Avvio più robusto**: un'opzione assente in `config.json` non manda più in
  crash l'app — i campi non impostati vengono letti come vuoti, non danno errore.
- **Nessun libro d'apertura impostato**: l'avvio non mostra più un warning
  fuorviante quando non è configurato alcun libro.

[1.2.2]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.2

## [1.2.1] - 2026-06-09

### Correzioni
- **Avvio su Windows con registro font corrotto**: alcune macchine hanno una
  voce non valida nel registro dei font di sistema; pygame vi enumerava sopra e
  l'app **crashava alla prima `SysFont`** (`TypeError: ... not int`). Ora
  l'avvio è blindato: le voci non valide vengono ignorate e, in extremis, si
  ripiega sul font di default — l'app parte comunque.

[1.2.1]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.1

## [1.2.0] - 2026-06-08

### Aggiunte
- **Suggestion for study**: il campo nick accetta **più nickname** (separati da
  `,` o `;`) e il matching è **case-insensitive** ovunque — comodo se giochi con
  più account o con maiuscole/minuscole diverse.
- **Analisi / Human Play**: la scacchiera ora è **fissa di default** (niente giro
  automatico a ogni mossa); il tasto **A** riattiva il flip automatico.
- **Nome unico "Hires Chess Trainer"** in tutta l'app, **menu riordinato** e
  **firma dell'autore** sullo splash all'avvio.

### Correzioni
- **Backspace** in analisi cancella l'**intera variante** in cui ti trovi (non
  più la singola mossa); **Canc** tronca senza più il flash sul no-op.
- Prompt di conferma di **Canc/Backspace** accorciati: non sforano più lo schermo.

### Interno
- Refactor importante: **tutti i modi di gioco** ora poggiano su un unico **core
  headless `BoardSession`** (logica/stato separati dal rendering) con una policy
  per modalità e validazione *validate-before-apply*; undo/troncamento/cancella-
  variante condivisi. Comportamento di gioco invariato. Suite a **179 test** verdi.

[1.2.0]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.0

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
