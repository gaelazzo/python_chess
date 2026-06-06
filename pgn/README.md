# `pgn/` — Le tue partite

Cartella di default per i file `.pgn` "generici": **partite tue scaricate**
o **partite analizzate / annotate**. Usata da diverse modalità:

- **Migliora dalle tue partite** (wizard): scarica qui le partite di
  Chess.com / lichess (es. `gaelazzo_chesscom.pgn`).
- **Tools → Download Chess.com / Download lichess games**: download
  incrementale append-only nello stesso file (dedup per URL `[Link]`).
- **Tools → Update learning base**: legge da qui i PGN da analizzare con
  il motore per trovare i blunder.
- **Analisi / Human Play**: tasto **S** salva qui (puoi navigare in
  un'altra cartella se vuoi). Tasto **L** carica da qui per scorrere /
  analizzare una partita.
- **Cosa studio adesso? (Study advisor)**: legge un PGN da qui per il
  ranking degli ECO da studiare.

## Cosa NON mettere qui

- **Repertorio d'apertura** → cartella `openings/`. Sono PGN con varianti
  esplicite che Study openings naviga come albero, non partite reali.
- **Studi di finale** → cartella `endgames/`. Sono posizioni
  individuali con header `[FEN]`, ognuna è un esercizio.

## Esempio di contenuto tipico

```
pgn/
├── gaelazzo_chesscom.pgn      # download incrementale Chess.com
├── gaelazzo_lichess.pgn       # download incrementale lichess
├── all.pgn                    # tutte le partite (anche merged)
├── all.pgn.idx                # cache statistiche di posizione (vedi sotto)
└── mie_analisi.pgn            # partite annotate manualmente
```

Il file `<pgn>.idx` (se presente) è la cache binaria delle statistiche di
posizione, costruita da `position_stats.py` la prima volta che usi il DB
come riferimento (tasto **Y** in Analisi). Si rigenera automaticamente se
modifichi il PGN. È in `.gitignore`.

> **Nota**: i file `.pgn` sono in `.gitignore` (i tuoi dati sono privati).
> Questo README viene committato.
