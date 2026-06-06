# `endgames/` — Studi di finale

🇬🇧 *English version:* [README.en.md](README.en.md)

Cartella dedicata ai **PGN di studi di finale** per la modalità *Allena
finali* (Menu principale → Allena finali → Choose endgame PGN).

## Cosa contiene

File `.pgn` dove **ogni "partita" è uno studio singolo**:

- Header `[SetUp "1"]` + `[FEN "..."]` definisce la posizione di partenza
  del finale.
- La mainline del PGN viene **ignorata** dal trainer: il giudice è la
  Syzygy tablebase (per posizioni ≤ 7 pezzi) con fallback Stockfish.
- I metadati `[White]` / `[Black]` / `[Event]` possono essere usati come
  titolo (es. `[White "Lucena"]`, `[Event "K+R vs K — opposition"]`).

## Esempio di partita

```pgn
[Event "Lucena position"]
[White "Bridge technique"]
[Black "Drawn?"]
[Result "*"]
[SetUp "1"]
[FEN "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"]

*
```

## Come si popola

- **Crea un PGN nuovo** in un editor di testo, oppure
- usa l'**editor posizione** di Analisi (tasto **U**) per costruire la
  posizione visualmente, poi **S** per salvare e scegliere il file
  `endgames/<nome>.pgn` come destinazione, oppure
- **esporta da ChessBase** o un altro tool che riesca a serializzare in
  PGN con header FEN.

## Cosa succede durante l'allenamento

1. Il programma sceglie una "partita" (= studio) random dal file.
2. La sua FEN diventa la posizione di partenza dell'esercizio.
3. Tu cerchi la mossa migliore; la TB / engine ti dice se è ottima o
   sbagliata.
4. Gli **errori** vengono salvati in una learning base
   `endgames_<filename>` in `data/`, drillabile da *Solve positions*.

## Esempio di contenuto tipico

```
endgames/
├── esempi.pgn                 # studi misti di base
├── finalitorre.pgn            # solo finali di torre
├── KBN_vs_K.pgn               # technique drill specifico
└── DEMbase_export.pgn         # esportazione dal Dvoretsky Endgame Manual
```

> **Nota**: i file `.pgn` sono in `.gitignore`. Questo README viene committato.
