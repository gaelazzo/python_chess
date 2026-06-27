# Changelog

Tutte le modifiche degne di nota a **Hires Chess Trainer**.
Formato ispirato a [Keep a Changelog](https://keepachangelog.com/);
versionamento [semantico](https://semver.org/lang/it/).

## [1.5.0] - 2026-06-27

### Aggiunte
- **Analisi dei buchi di repertorio (tasto `X`)** in modalità analisi: mentre
  editi un PGN-repertorio, `X` salta al prossimo "buco" — una risposta avversaria
  **forte** (giocata dai master sopra una soglia) che compare nelle tue partite
  (il *DB di riferimento*) ma a cui il repertorio **non ha una risposta**,
  trasposizioni escluse. La scacchiera si posiziona sul nodo da sistemare,
  `Shift+X` riscansiona dopo aver aggiunto linee, `Esc` chiude l'avviso.
- **"Opening book" in *Play vs computer***: opzionalmente il motore segue un tuo
  repertorio (cartella `openings/`), giocando una risposta prevista **a caso**
  (trasposizioni riconosciute) con una **deviazione occasionale** (~1 volta su 6);
  finite le mosse di libro prosegue **da motore** alla forza scelta. Alleni
  l'apertura dentro una partita vera.
- **Tasto `G`**: quando i dati masters sono troppo pochi per un piano chiaro,
  mostra comunque le **mosse dei master con la frequenza** (come il tasto `D`).
- **Interruzione con `ESC`** dell'analisi lunga nei wizard *Migliora dalle tue
  partite* e *Suggestion for study* (finisce la partita in corso, salva e si ferma).

### Modifiche
- **Avviso modifiche non salvate**: chiudendo la finestra o tornando al menu
  durante l'analisi con un PGN modificato, l'app chiede conferma prima di scartare.
- Manuale d'uso (README IT/EN) allineato alle funzioni attuali.

### Correzioni
- *Migliora dalle tue partite*: dopo un download **incrementale** ora analizza
  **solo le partite nuove** (prima rianalizzava l'intero file, gonfiando il
  contatore N/M e ripetendo lavoro già fatto).

## [1.4.0] - 2026-06-19

### Aggiunte
- **Toolbar a icone** in tutti i modi, con remap dei tasti e la valutazione del
  motore mostrata nel pannello CPU.
- **Piani d'apertura dai maestri (tasto `G`)**: dal database *masters* di Lichess
  estrae i piani tipici per lato (gruppi di mosse che ricorrono insieme), ciascuno
  con uno score e la risposta condizionata dell'avversario (W/D/L per risposta).
  I piani sono numerati: premendo **1–9** le mosse della variante compaiono come
  **frecce** sulla scacchiera (bianche per il Bianco, nere per il Nero), **0** le
  toglie. Cache su disco delle interrogazioni (istantanea dopo la prima volta) e
  parametri configurabili nel Setup. Il risultato precompila il dossier **idee**
  della struttura (tasto `I`).
- **Statistiche database Lichess (tasto `D`)**: query secca della distribuzione
  delle mosse (tutti i giocatori, non masters) con W/D/L per la posizione corrente.
- **Gestione trasposizioni in analisi**: avviso quando una mossa traspone in una
  posizione già presente; blocco dell'analisi duplicata (da una posizione duplicata
  non si aggiungono nuove mosse); bottone **Twins** / tasto **N** per ciclare tra i
  "gemelli"; **J** salta all'originale; **Shift+J** cerca una posizione per FEN.
- **Commenti mossa multi-riga (tasto `T`)**: editor su più righe (Invio = a capo,
  Ctrl+Invio = salva); gli a-capo sono preservati nel PGN.
- **INSTALL.md**: elenco di fonti di libri d'apertura Polyglot (`.bin`) gratuiti.

### Correzioni
- I libri d'apertura **commerciali** (ChessBase/Fritz) non vengono mai inclusi nel
  pacchetto distribuito: bonifica e blindatura del packaging.
- Le **icone della toolbar** ora sono incluse nel pacchetto PyInstaller
  (`images/icons/`): prima mancavano dal build.

[1.4.0]: https://github.com/gaelazzo/python_chess/releases/tag/v1.4.0

## [1.2.5] - 2026-06-12

### Aggiunte
- **Suggestion for study — niente doppi conteggi al riesame**: rianalizzando lo
  stesso PGN, le partite già analizzate vengono saltate (per ciascun giocatore si
  ricorda la finestra di date già esaminata, salvata nella base). Così i contatori
  degli errori non si gonfiano e le posizioni già "imparate" non riemergono.

### Modifiche
- **"PGN moves" mostra il prossimo bivio**: la prossima mossa principale e le
  eventuali varianti alternative *a quella mossa*, così navigando vedi in anticipo
  una diramazione (prima mostrava il proseguio della linea).
- **Font più leggibili** per il registro mosse, "PGN moves" e "Book moves".

### Correzioni
- **Analisi del motore che sforava**: durante l'allenamento le righe del motore
  non escono più dal riquadro CPU sui pannelli laterali.
- **Sfarfallio dei pannelli** "Book moves" / "Personal Stats" / "PGN moves" al
  passaggio del mouse sulla scacchiera.

[1.2.5]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.5

## [1.2.4] - 2026-06-10

### Aggiunte
- **Pannello "Personal Stats"** in Analisi (tasto **Y** o pulsante *Stats*):
  per la posizione corrente mostra quante volte è comparsa nel tuo database di
  riferimento, con percentuali Bianco/Patta/Nero e le continuazioni più giocate,
  in colonne allineate e leggibili.
- **"PGN moves" mostra il proseguio della linea**: le mosse successive in
  notazione SAN, non più solo la mossa immediatamente seguente.

### Modifiche
- **Nuovo layout dei pannelli laterali**: l'elenco "PGN moves" è ora sotto il
  registro delle mosse; lo spazio liberato ospita il pannello Personal Stats.
- **Registro mosse più ordinato**: una mossa per riga (notazione canonica) e
  scorrimento automatico, così le ultime mosse giocate restano sempre visibili.

### Correzioni
- **Apertura file PGN**: quando ricompare il nome dell'ultimo file scelto, ora è
  sempre effettivamente caricabile (memoria del file separata per ciascuna
  modalità: aperture, finali, carica/salva).
- **Righe "fantasma"**: i pannelli laterali non lasciano più testo residuo in
  fondo quando si naviga tra le mosse.

[1.2.4]: https://github.com/gaelazzo/python_chess/releases/tag/v1.2.4

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
