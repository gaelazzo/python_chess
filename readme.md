#Hires Chess Trainer

Hires Chess Trainer è un'applicazione che ti aiuta a imparare a giocare a scacchi.
E' possibile usarla in diverse modalità:
- Studio aperture
- Ripasso aperture
- Correzione errori tattici / Esercizi di tattica
- Correzione errori di apertura
- Ripasso lezioni assistito da Brainmaster (AI)



## Learning Base

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