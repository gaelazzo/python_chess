# `openings/` — Repertorio d'apertura

🇬🇧 *English version:* [README.en.md](README.en.md)

Cartella dedicata ai **PGN di repertorio d'apertura** per la modalità
*Study openings* (Menu principale → Study openings → Choose opening PGN).

## Cosa contiene

File `.pgn` strutturati come **alberi di varianti**, NON come partite reali:

- Ogni file rappresenta tipicamente UN'apertura (es. `C42Russian.pgn`,
  `c96.pgn`) o un sottosistema di un'apertura.
- Le tue mosse (del lato che giochi) costituiscono la mainline.
- Le mosse dell'avversario sono codificate come **varianti** del PGN —
  l'app le naviga come alternative casuali.
- Niente header `[FEN]`: si parte sempre dalla posizione iniziale standard.

## Esempio di partita / linea

```pgn
[Event "C42 Russian — White's repertoire"]
[White "Repertoire White"]
[Black "Repertoire Black"]
[Result "*"]

1. e4 e5 2. Nf3 Nf6 (2... Nc6 3. Bb5) 3. Nxe5 (3. d4 *) d6 4. Nf3 Nxe4
5. d4 d5 *
```

In Study openings: tu giochi il Bianco, le tue mosse della mainline (1.e4,
2.Nf3, 3.Nxe5...) sono "vincolate" — devi indovinarle. Le mosse del Nero
sono varianti dal punto di vista del PGN: il programma sceglie a random
fra le alternative memorizzate (2...Nf6 vs 2...Nc6, ecc.).

## Auto-detect del colore

L'app conta tutte le varianti del file e prende la maggioranza:
- Varianti `(N... mossa)` = alternative del Nero → utente gioca **Bianco**.
- Varianti `(N. mossa)` = alternative del Bianco → utente gioca **Nero**.
- Pareggio o nessuna variante → default Bianco.

## Come si popola

- **Costruisci tu** un PGN nell'editor di Analisi: parti da una posizione,
  inserisci le tue mosse, aggiungi varianti dell'avversario con il mouse,
  poi **S** per salvare in `openings/<nome>.pgn`.
- **Copia un PGN esistente** (libri di apertura, database online) e
  inseriscilo qui.
- **Esporta da ChessBase** o tool simili nelle sezioni "apertura" del tuo
  catalogo.

## Cosa succede durante l'allenamento

1. Il programma pesca una linea random dal PGN (Lead-in = Skip oppure
   Replay, vedi readme principale §3.6).
2. Tu trovi la mossa giusta a ogni turno; il programma risponde con una
   delle alternative dell'avversario.
3. Gli **errori** vengono salvati in `openings_<filename>` in `data/`,
   drillabile da *Solve positions*.

## Esempio di contenuto tipico

```
openings/
├── C42Russian.pgn             # difesa russa per il Nero
├── c96.pgn                    # variante chiusa Spagnola
├── CaroKan.pgn                # tua linea di Caro-Kann
└── KingsIndian.pgn            # apertura Re-India per il Bianco
```

> **Nota**: i file `.pgn` sono in `.gitignore`. Questo README viene committato.
