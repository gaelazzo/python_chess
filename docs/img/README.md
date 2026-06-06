# Immagini per i README / README assets

Questa cartella contiene le immagini mostrate in [readme.md](../../readme.md)
e [README.en.md](../../README.en.md).

## File attesi

| File | Uso | Stato |
|------|-----|-------|
| `demo.gif` | GIF "hero" in cima ai README (il flusso principale) | **da registrare** |
| `screenshot-menu.png` | (opzionale) menu principale | da fare |
| `screenshot-analysis.png` | (opzionale) schermata di analisi con varianti | da fare |
| `screenshot-solve.png` | (opzionale) *Solve positions* su una learning base | da fare |

> Finché `demo.gif` non esiste, i README usano `pic-chess.png` (lo splash) come
> immagine provvisoria. Una volta pronta la GIF, basta cambiare **una riga** in
> ciascun README: sostituisci `src="pic-chess.png"` con
> `src="docs/img/demo.gif"` (cerca il commento `TODO`).

## Come registrare `demo.gif` (Windows)

1. Installa **[ScreenToGif](https://www.screentogif.com/)** (gratuito, ideale
   per questo scopo).
2. Avvia Hires Chess Trainer e registra **il flusso che vende il programma**,
   cioè *Improve from your games*:
   - Menu principale → **Improve from your games**;
   - compila utente + opzioni, **Start** → si vede la barra `N/M` di analisi;
   - al termine, clic su **Train tactics/openings** → arrivi su *Solve
     positions* e **risolvi una posizione** (mossa giusta = feedback verde).
3. Tieni la clip **breve (~10-15 s)**: è un trailer, non un tutorial.

## Ottimizzazione (importante per GitHub)

- Larghezza **≤ 720 px** (i README usano `width="640"`).
- Riduci a **~10-12 fps** e usa l'ottimizzatore di ScreenToGif.
- Punta a un file **< 8 MB**: GIF più grandi GitHub a volte non le mostra
  inline e rallentano il caricamento del README.
- In alternativa alla GIF puoi usare un **MP4** caricato direttamente nella
  pagina di una *Release* o in una issue, e linkarlo — pesa molto meno.

## Nota

I file immagine (`*.png`, `*.gif`) **non** sono in `.gitignore`: vengono
committati normalmente insieme ai README.
