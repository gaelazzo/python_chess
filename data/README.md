# `data/` — Learning bases

Cartella delle **learning base**: posizioni da studiare/ripassare con le
statistiche dei tuoi tentativi. Letta automaticamente all'avvio (vedi
`LearningBase.py`) e popolata dalle modalità di allenamento.

## Cosa contiene

Ogni learning base è composta da **due file**:

| File | Contenuto |
|------|-----------|
| `base_<nome>.json` | Metadati: `movesToAnalyze`, `blunderValue`, `ponderTime`, `useBook`. |
| `<nome>.csv` | Una posizione per riga: `zobrist`, `fen`, `ok`, `move`, `moves`, `ntry`, `successful`, `severity`, `serie`, `skip`, ecc. |

L'app carica tutto ciò che matcha `base_*.json` (il prefisso `base_` viene
rimosso dal nome). Le basi compaiono nel dropdown di *Solve positions* e
*BrainMaster lessons*.

## Come si popolano (NON editare a mano)

Niente editing manuale dei CSV — i file sono gestiti dal programma:

- **Tools → Create learning base**: crea una base vuota.
- **Tools → Update learning base**: il motore analizza un PGN, trova i
  blunder e li aggiunge.
- **Tools → Unroll PGN file**: trasforma ogni posizione di un PGN in una
  voce della base (utile per drillare un'apertura completa).
- **Migliora dalle tue partite** (wizard): orchestrazione automatica di
  download + analisi + creazione di `<utente>_tactics` e
  `<utente>_openings`.
- **Allena finali / Study openings**: ogni errore commesso viene salvato
  rispettivamente in `endgames_<filename>` e `openings_<filename>`.
- **Analisi → tasto K**: salva manualmente (posizione + mossa corretta) in
  una base scelta da te.

## Cosa NON contiene

- File PGN (vanno in `pgn/`, `endgames/`, `openings/` a seconda dell'uso).
- File `.idx` (cache statistiche posizione: stanno accanto al PGN di
  riferimento).

## Backup

Se qualcosa va storto, basta copiare l'intera cartella `data/` per
preservare tutto il tuo storico di apprendimento.

> **Nota**: l'intera cartella `data/` è in `.gitignore` (i tuoi dati sono
> privati). Questo README è whitelistato — è l'unico file di `data/` che
> viene committato.
