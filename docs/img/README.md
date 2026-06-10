# Immagini per i README / README assets

Questa cartella contiene le immagini mostrate in [README.md](../../README.md)
e [README.it.md](../../README.it.md).

## File attesi

| File | Uso | Stato |
|------|-----|-------|
| `demo.gif` | GIF "hero" gameplay (flusso *Solve positions*) | **da registrare** |
| `screenshot-menu.gif` | immagine hero attuale + menu | ✅ presente |
| `screenshot-analysis.gif` | galleria — analisi con engine + libro | ✅ presente |
| `screenshot-openings.gif` | galleria — studio aperture in azione | ✅ presente |
| `screenshot-notation.gif` | galleria — pannello notazione/varianti | ✅ presente |

> L'immagine hero in cima ai README è ora `analisi.gif` (clip dell'Analisi).
> `screenshot-menu.gif` resta nel repo ma non è più mostrata inline; per
> cambiare hero, modifica la riga `<img src="docs/img/...">` in ciascun README.

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
