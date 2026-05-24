# Hires Chess Trainer — Manuale d'uso

🇬🇧 *English version:* [README.en.md](README.en.md)

**Hires Chess Trainer** è un'applicazione desktop per allenarsi e migliorare a scacchi.
Permette di giocare contro il computer o contro un altro umano, di **analizzare**
partite con varianti e annotazioni, e di **studiare** posizioni ed errori tramite
"learning base" e lezioni (anche assistite dal servizio AI *BrainMaster*).

---

## Indice
➡️ **Sei nuovo?** Parti da [Primi passi: ricette pratiche](#primi-passi-ricette-pratiche).

1. [Avvio e requisiti](#1-avvio-e-requisiti)
2. [Il menu principale](#2-il-menu-principale)
3. [Le modalità](#3-le-modalità)
4. [Comandi durante una partita](#4-comandi-durante-una-partita)
5. [Analizzare una partita: varianti, annotazioni, commenti](#5-analizzare-una-partita)
6. [Il pannello Notazione](#6-il-pannello-notazione)
7. [Salvare e caricare partite](#7-salvare-e-caricare-partite)
8. [Strumenti (Tools)](#8-strumenti-tools)
9. [Concetti chiave](#9-concetti-chiave)
10. [File e cartelle](#10-file-e-cartelle)
11. [Appendice tecnica](#appendice-tecnica-struttura-della-learning-base)

---

## 1. Avvio e requisiti

Avvia il programma con:

```
python chessMain.py
```

Per funzionare al meglio servono (configurabili da **Tools → Setup**, vedi §8):
- un **motore UCI** (es. Stockfish) nella cartella `engines/` — usato per l'analisi e per il gioco contro il computer;
- (opzionale) un **libro di aperture** Polyglot (`.bin`) nella cartella `books/`;
- (opzionale) l'indirizzo del servizio **BrainMaster** (`base_url`) e l'`id studente`, se vuoi usare le lezioni assistite.

All'avvio appare il **menu principale**; ci si sposta con il **mouse** o le frecce e si conferma con **Invio**.

---

## Primi passi: ricette pratiche

*Se è la prima volta che usi il programma, parti da qui: queste sono le attività
più comuni, passo per passo.*

### Ricetta 0 — Configurazione iniziale (una volta sola)
1. **Tools → Setup → Choose engine**: seleziona il motore UCI (es. `stockfish.exe`)
   dalla cartella `engines/`. Senza motore, analisi e gioco contro il computer non funzionano.
2. *(Facoltativo)* **Choose book**: seleziona un libro di aperture `.bin` da `books/`.
3. *(Facoltativo, per le lezioni)* compila **base_url** e **id studente** del servizio BrainMaster.

### Ricetta A — Correggere i propri errori (come Bianco o come Nero)
*Obiettivo: ripassare le posizioni in cui hai sbagliato nelle tue partite.*
1. **Scarica le tue partite** — Tools → Download Chess.com games:
   - *PGN file to create*: un nome, es. `mie_bianche`;
   - *player*: il tuo username Chess.com;
   - *Player color*: **White** per gli errori col Bianco (usa **Black** per quelli col Nero);
   - **Download games**.
2. **Crea una learning base vuota** — Tools → Create learning base:
   - *filename*: es. `errori_bianco`;
   - *blunderValue*: soglia d'errore in centesimi di pedone (es. `80` ≈ 0.8 di pedone peggio della mossa migliore);
   - *movesToAnalyze*, *ponderTime*: quante mosse analizzare e quanto tempo dare al motore;
   - **Create learning base**.
3. **Popola la base con i tuoi errori** — Tools → Update learning base:
   - *player*: il tuo username; *Choose PGN file*: `mie_bianche`; *Choose base file*: `errori_bianco`;
   - **Update Learning Base** (il motore analizza le tue mosse e registra le posizioni sbagliate).
4. **Ripassa** — Menu principale → Solve positions → *Choose base file*: `errori_bianco` → **Play**.
   Ti vengono riproposte quelle posizioni: gioca la mossa giusta (**H** mostra la soluzione).
5. Ripeti con **Player color = Black** per gli errori col Nero (in una base separata, es. `errori_nero`).

### Ricetta B — Studiare un'apertura / creare "modelli"
*Obiettivo: allenare un repertorio d'apertura.*
- **Procurati il PGN dell'apertura**, in due modi:
  - (a) copia un file `.pgn` esistente (con le linee dell'apertura) nella cartella `pgn/`; **oppure**
  - (b) **costruiscilo tu**: *Play between humans*, gioca le mosse dell'apertura, aggiungi
    **varianti** (gioca mosse alternative col mouse), eventualmente annota (**N**) e commenta
    (**T**), poi **Salva (S)** in un file PGN.
- **Allenati sul repertorio** — Menu principale → Study openings → *Choose PGN file*
  (il tuo PGN) + *You play* (White/Black) → **Play**: il computer gioca le linee memorizzate
  e tu devi trovare la mossa giusta.
- **(In alternativa) trasformalo in base di studio** — Tools → Create learning base
  (es. `apertura_x`) → Tools → **Unroll PGN file** (*Choose PGN* + *You play* il tuo colore
  + *Choose base*) → poi ripassala con **Solve positions**.

### Ricetta C — Analizzare una partita con varianti e annotazioni
1. Menu principale → **Play between humans**.
2. Carica una partita (**L**) oppure giocala; scorri con **←/→**.
3. Prova mosse alternative **col mouse** → vengono aggiunte come varianti.
4. Annota la qualità (**N**) e aggiungi commenti (**T**).
5. Guarda tutto nel **pannello Notazione** (**V**); naviga con ←/→ e ↑/↓.
6. **Salva (S)** o copia il PGN (**G**) per riprenderla in seguito.

### Ricetta D — Lezioni a ripetizione spaziata (BrainMaster)
*(Richiede `base_url` configurato in Setup.)*
1. Crea una learning base (Ricetta A o B).
2. Tools → **Create Course for BrainMaster** → *Choose base file* → **Create** (registra la
   base come corso). *(In alternativa: Tools → Unroll PGN file as lesson.)*
3. Menu principale → **BrainMaster lessons** → scegli il corso → **Exercise**: il servizio
   decide quali posizioni riproporti e quando.

---

## 2. Il menu principale

| Voce | Cosa fa |
|------|---------|
| **Play against computer** | Gioca una partita contro il motore. |
| **Play between humans** | Due giocatori umani sulla stessa scacchiera. È anche la **modalità di analisi** (qui puoi inserire varianti e annotazioni). |
| **Solve positions** | Ripassa le posizioni (errori) salvate in una *learning base*. |
| **BrainMaster lessons** | Lezioni guidate dal servizio BrainMaster *(appare solo se hai configurato `base_url`)*. |
| **Study openings** | Esercitati su partite "modello": devi trovare tu la mossa migliore. |
| **Tools** | Creazione/aggiornamento di learning base, import PGN/Chess.com, Setup. |
| **Quit** | Esce dal programma (anche premendo **`Q`** o chiudendo la finestra). |

---

## 3. Le modalità

### 3.1 Play against computer
Imposta i parametri e premi **Play**:
- **You play**: White / Black / Random (con chi giochi tu);
- **ELO**: forza del motore (1350–2850);
- **ELO MAX**: se attivo, il motore gioca alla massima forza ignorando l'ELO.

Muovi con il mouse; il computer risponde automaticamente.

### 3.2 Play between humans (analisi)
Due umani giocano a turno sulla stessa scacchiera. Poiché **non c'è un motore che
risponde**, questa è la modalità giusta per **analizzare**: puoi tornare indietro,
provare mosse alternative (varianti), annotarle e commentarle (vedi §5 e §6).

### 3.3 Solve positions
> **Una posizione, una mossa.** Ti viene proposta una posizione e devi giocare la
> mossa giusta. Adatto a ripassare *qualsiasi cosa* (errori, tattica, finali…).

Ripassa le posizioni salvate in una *learning base* (tipicamente i tuoi errori).
Parametri:
- **ECO (optional)**: filtra per codice di apertura;
- **You play**: White / Black / Any;
- **Choose base file**: scegli la learning base;
- **Skip initial moves** / **Num Moves to Show**: quante mosse iniziali mostrare prima di chiederti la mossa.

Ti viene mostrata una posizione: **gioca la mossa che ritieni corretta**. Il programma
ti dice se è giusta; con **H** puoi vedere la soluzione.

### 3.4 BrainMaster lessons
Come sopra, ma le posizioni e l'ordine di ripasso sono suggeriti dal servizio
**BrainMaster** (ripetizione spaziata). Scegli il **corso** e premi **Exercise**.
*(Visibile solo se hai configurato `base_url` in Setup.)*

### 3.5 Study openings
> **Una linea intera.** Giochi tu l'intera sequenza dalla tua parte (le tue mosse
> sono fisse), mentre il computer può rispondere con **varianti diverse** tra quelle
> memorizzate. Tipico per **ripetere le aperture** / un repertorio.

Carichi un file PGN di linee "modello". Il computer gioca una delle linee
memorizzate e **tu devi trovare la mossa migliore** a ogni turno.
- **You play**: White / Black;
- **Choose PGN file**: il file con le partite modello;
- **Skip initial moves** / **Num Moves to Show**: mosse iniziali da mostrare.

---

## 4. Comandi durante una partita

Durante una partita (Play against computer / between humans) valgono questi comandi.
**Tieni premuto il tasto destro del mouse** per vedere l'aiuto a schermo.

| Tasto | Azione |
|-------|--------|
| **clic mouse** | Seleziona la casella di partenza e quella di arrivo per muovere |
| **tasto destro** (tenuto) | Mostra il pannello di aiuto |
| **←** | Torna indietro di una mossa |
| **→** | Vai alla mossa successiva (se ci sono più varianti, le scegli da un menu) |
| **C** | Copia la posizione corrente (FEN) negli appunti |
| **G** | Copia l'intera partita (PGN, con varianti e annotazioni) negli appunti |
| **S** | Salva la partita |
| **A** | Modalità analisi (blocca l'orientamento della scacchiera) |
| **F** | Ruota la scacchiera |
| **R** | Reset (nuova partita) |
| **E** | Motore di analisi ON/OFF (mostra la valutazione) |
| **B** | Mostra/nascondi il libro di aperture |
| **D** | Mostra/nascondi la lista mosse |
| **Q** | Torna al menu principale |

**Solo in "Play between humans" (analisi):**

| Tasto | Azione |
|-------|--------|
| **L** | Carica una partita (parte dalla prima mossa, da scorrere con →) |
| **N** | Annota l'ultima mossa con un glifo (`!`, `?`, `!!`, `??`, `!?`, `?!`, `±`, …) |
| **T** | Aggiungi un commento testuale all'ultima mossa |
| **V** | Apri il pannello **Notazione** (intera partita + varianti) |

> Nelle modalità di studio (Solve positions / BrainMaster / Study openings) i comandi
> sono simili ma orientati alla soluzione: **Q** esci, **C/G** copia, **E/B/D** pannelli,
> **+** mostra qualche mossa in più (suggerimento), **H** mostra la soluzione.

---

## 5. Analizzare una partita

In **Play between humans** puoi costruire e annotare l'analisi di una partita.

**Inserire varianti.** Spostati su una posizione (con ←/→), poi **gioca col mouse una
mossa diversa** da quella già presente: viene aggiunta automaticamente come **variante**
a partire da quel punto. Le mosse già presenti si seguono con **→** (se ci sono più
continuazioni appare un menu di scelta).

**Annotare la qualità di una mossa (tasto `N`).** Apre un menu con i glifi standard;
quello scelto viene mostrato accanto alla mossa nella lista (es. `2. Nf3!`). Una mossa
ha **una sola** valutazione: sceglierne un'altra sostituisce la precedente; *(remove all)*
la rimuove. Glifi disponibili:

| Glifo | Significato | Glifo | Significato |
|-------|-------------|-------|-------------|
| `!` | buona mossa | `=` | posizione pari |
| `?` | errore | `∞` | poco chiara |
| `!!` | mossa eccellente | `⩲` / `⩱` | Bianco / Nero leggermente meglio |
| `??` | grave errore | `±` / `∓` | Bianco / Nero meglio |
| `!?` | interessante | `+−` / `−+` | Bianco / Nero vincente |
| `?!` | dubbia | `□` | mossa forzata |

**Commentare una mossa (tasto `T`).** Apre un campo di testo: scrivi il commento e
premi **Save**. Il commento appare nella lista mosse (in giallo) e nel pannello Notazione.

**Persistenza.** Glifi e commenti sono salvati nel PGN: con **S** (salva) o **G** (copia
PGN) restano nella partita e si ritrovano riaprendola, anche in altri programmi di scacchi.

---

## 6. Il pannello Notazione

Premi **`V`** (in Play between humans) per aprire una vista a schermo intero con
**l'intera partita**: linea principale e **varianti indentate ad albero**, con glifi e
commenti. In basso a destra una **mini-scacchiera** mostra la posizione selezionata.

| Comando | Azione |
|---------|--------|
| **←** / **→** | Mossa precedente / successiva |
| **↑** / **↓** | Riga precedente / successiva (passa tra linea principale e varianti) |
| **rotella**, **PgUp/PgDn**, **Home/End** | Scorri la vista |
| **clic su una mossa** | Vai a quella posizione (chiude il pannello) |
| **V** / **Esc** | Chiudi il pannello |

Navigando, la mossa evidenziata e la mini-scacchiera si aggiornano; alla chiusura la
scacchiera principale resta sulla mossa selezionata.

---

## 7. Salvare e caricare partite

- **Salva** (tasto **S**): apri il menu Save, scegli/crea il file PGN e i dati della
  partita (giocatori, evento, ecc.), poi **Save**. Le partite sono salvate in `pgn/`.
- **Carica** (tasto **L**, solo in Play between humans): scegli il file PGN e la partita
  dall'elenco. La partita viene caricata **dall'inizio**, così puoi scorrerla con **→**
  ed esplorarne le varianti.

---

## 8. Strumenti (Tools)

| Strumento | A cosa serve |
|-----------|--------------|
| **Download Chess.com games** | Scarica le partite di un giocatore da Chess.com in un file PGN (indica file da creare, *player* e colore). |
| **Create learning base** | Crea una nuova learning base vuota: `movesToAnalyze`, `blunderValue` (soglia errore in centipawn), `ponderTime`, `useBook`, `filename`. |
| **Update learning base** | Analizza le partite di un *player* in un PGN e **registra gli errori** nella base scelta (correzione errori). |
| **Unroll PGN file** | Trasforma un PGN in un insieme di **posizioni** dentro una learning base. |
| **Unroll PGN file as lesson** | Come sopra, ma come **lezione** (per il ripasso/BrainMaster). |
| **Create Course for BrainMaster** | Registra una learning base come **corso** BrainMaster *(se `base_url` configurato)*. |
| **Setup** | Configura: `base_url` e `id studente` (BrainMaster), **Choose engine** (motore UCI), **Choose book** (libro di aperture). |

---

## 9. Concetti chiave

- **Learning base** — un archivio di posizioni da studiare con le statistiche dei tuoi
  tentativi. Vedi l'appendice tecnica per il formato. Tipicamente contiene i tuoi errori
  (creata con *Update learning base*) o posizioni estratte da partite (*Unroll PGN*).
- **BrainMaster** — servizio esterno (AI) che propone le posizioni da ripassare con
  ripetizione spaziata; richiede `base_url` e `id studente`.
- **ECO** — codice standard che identifica un'apertura (es. `C42`); usato per filtrare.
- **ELO** — misura della forza di gioco; per il computer si imposta in *Play against computer*.
- **FEN / PGN** — notazioni standard: FEN descrive una singola posizione, PGN un'intera
  partita (con varianti, glifi e commenti).
- **Glifi (NAG)** — i simboli di annotazione `! ? !? ± …` (vedi §5).

---

## 10. File e cartelle

| Cartella | Contenuto |
|----------|-----------|
| `data/` | Learning base (`base_<nome>.json` + `<nome>.csv`) |
| `pgn/` | Partite salvate e file PGN importati |
| `engines/` | Motori UCI (es. Stockfish) |
| `books/` | Libri di aperture Polyglot (`.bin`) |

---

# Appendice tecnica: struttura della Learning Base

La *Learning Base* è la struttura dati che memorizza le posizioni da studiare/allenare
e tiene traccia dei progressi dell'utente su ciascuna di esse. È implementata in
[LearningBase.py](LearningBase.py).

### Organizzazione su disco

Ogni learning base è composta da **due file** salvati nella cartella `data/`:

| File | Contenuto |
|------|-----------|
| `base_<nome>.json` | Metadati/parametri della base (serializza `LearningBaseData`) |
| `<nome>.csv` | Elenco delle posizioni, una per riga (serializza i `LearnPosition`) |

All'avvio il modulo carica automaticamente tutte le basi presenti: cerca i file
`base_*.json` nella cartella `data/`, li carica e li espone nel dizionario
`learningBases`, indicizzato per nome (il prefisso `base_` viene rimosso da
`stripBaseName`). Se la cartella `data/` non esiste viene creata.

### `LearningBase` (la base)

Classe contenitore. Mantiene il dizionario delle posizioni e i parametri di analisi.

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `positions` | `Dict[int, LearnPosition]` | Posizioni, indicizzate per hash Zobrist |
| `movesToAnalyze` | `int` | Numero di mosse da analizzare |
| `blunderValue` | `int` | Soglia (in centipawn) per considerare una mossa un errore |
| `ponderTime` | `float` | Tempo di analisi/pondering del motore |
| `useBook` | `bool` | Se usare il libro di aperture |
| `filename` | `Optional[str]` | Nome base dei file su disco |

I metadati (`movesToAnalyze`, `blunderValue`, `ponderTime`, `useBook`, `filename`)
vengono incapsulati in `LearningBaseData` per il salvataggio nel file JSON, mentre le
posizioni vengono scritte separatamente nel file CSV.

Metodi principali:
- `load(filename)` / `save(filename)` — caricamento e salvataggio (JSON + CSV).
- `addPosition(game, board, goodMove)` — aggiunge una nuova posizione (se non già presente).
- `updatePosition(moveMade, goodMove, game, board)` — analizza la mossa giocata
  dall'utente e aggiorna le statistiche della posizione.
- `updatePositionStats(position, moveMade, date)` — logica di aggiornamento delle
  statistiche; restituisce `True` se la mossa giocata è quella corretta.

### `LearnPosition` (la singola posizione)

Dataclass che rappresenta una posizione di studio. Ogni riga del CSV corrisponde a un
`LearnPosition`.

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `zobrist` | `int` | Hash Zobrist della posizione (chiave univoca) |
| `fen` | `str` | Posizione in notazione FEN |
| `ok` | `str` | Mossa corretta (UCI) attesa in questa posizione |
| `move` | `str` | Mossa effettivamente giocata |
| `moves` | `str` | Sequenza di mosse UCI che portano alla posizione |
| `successful` | `int` | Numero di tentativi riusciti |
| `ntry` | `int` | Numero totale di tentativi |
| `white` | `str` | Giocatore con il Bianco (dalla partita di origine) |
| `black` | `str` | Giocatore con il Nero (dalla partita di origine) |
| `eco` | `Optional[str]` | Codice ECO dell'apertura |
| `gamedate` | `Optional[date]` | Data della partita di origine |
| `lastTry` | `Optional[date]` | Data dell'ultimo tentativo |
| `firstTry` | `Optional[date]` | Data del primo tentativo |
| `serie` | `int` | Contatore della serie corrente (positivo = successi consecutivi, negativo = errori) |
| `skip` | `bool` | Posizione "imparata", da saltare nel ripasso |
| `idquiz` | `Optional[int]` | Identificativo del quiz associato (opzionale) |

`LearnPosition` offre anche metodi di conversione verso PGN (`to_Pgn`, `to_PgnString`)
e da dizionario (`from_dict`, usato per leggere le righe del CSV).

### Logica di apprendimento

Quando l'utente gioca una mossa, `updatePositionStats` aggiorna la posizione:
- incrementa `ntry` e aggiorna `firstTry`/`lastTry`;
- se la mossa coincide con `ok`, incrementa `successful` e la `serie` di successi;
  raggiunti **5 successi consecutivi** (`serie >= 5`) la posizione viene marcata come
  imparata (`skip = True`);
- se la mossa è errata, la `serie` diventa negativa (azzerando l'eventuale streak positivo).

---

## Architettura del codice (per sviluppatori)

Il codice è organizzato in moduli a responsabilità singola (refactoring di `chessMain.py`):

| Modulo | Ruolo |
|--------|------|
| `chessMain.py` | Orchestratore: costruisce il menu (`mainMenu`) e avvia il loop (`runMain`) |
| `app_context.py` | Stato dell'infrastruttura pygame (schermo, manager, font, clock…) come oggetto `app` |
| `state.py` | Stato di sessione condiviso (parametri, costanti) |
| `game_loop_common.py` | Helper condivisi dai loop di gioco (overlay aiuto, toggle pannelli, clipboard) |
| `menu_helpers.py` | Costruttori dei menu (selettori file, callback, ecc.) |
| `save_load.py` | Salvataggio/caricamento partite e relativi menu |
| `learningbase_admin.py` | Creazione/aggiornamento learning base, import PGN/Chess.com |
| `notation.py` | Pannello Notazione (vista albero + mini-scacchiera) |
| `modes/` | Le modalità di gioco: `play_game`, `brainmaster`, `replay`, `models` (+ `common`) |
| `GameState.py` | Stato della partita, albero PGN, mosse, annotazioni |
| `BoardScreen.py` | Disegno della scacchiera e dei pannelli |
| `UCIEngines.py`, `book.py` | Motore UCI e libro di aperture |

I test sono in `tests/` (eseguire con `python -m pytest`).
