# Immagini per i README / README assets

Questa cartella contiene le immagini mostrate in [README.md](../../README.md)
e [README.it.md](../../README.it.md).

## File in questa cartella

I file qui sotto sono quelli che **esistono davvero** e che i README usano.

**Clip animati** (registrazione **manuale** con ScreenToGif):

| File | Uso | Stato |
|------|-----|-------|
| `analisishort.gif` | **clip hero** in cima ai README (Analisi in azione) | ✅ aggiornato (rifatto a mano il 2026-06-15 con la UI a icone) |

> (Le vecchie `analisi.gif` / `analisi.mp4`, mai referenziate da alcun README,
> sono state rimosse.)

**Screenshot PNG**:

| File | Uso | Come si aggiorna |
|------|-----|------------------|
| `stats.png` `solve.png` `openings.png` `endgame.png` `notation.png` `setup.png` | schermate di analisi/gioco nei README | ✅ **automatico**: `python capture_screenshots.py` |
| `advisor.png` | Study advisor (screenshot a dati reali dell'autore) | manuale (solo `--preview` rigenera una versione mock) |
| `menu.png` `tools.png` `improve.png` | schermate `pygame_menu` (menu principale, Tools, Improve) | manuale (non coperte dal tool) |

> L'hero in cima ai README è `analisishort.gif` (riga
> `<img src="docs/img/analisishort.gif" ...>` in ciascun README), già aggiornato
> alla UI a icone. I **PNG** di analisi/gioco si rigenerano col tool; il GIF hero
> è manuale (vedi sotto se in futuro va rifatto).
>
> Nota: nomi tipo `screenshot-*.gif` o `demo.gif` citati in vecchie versioni di
> questo file **non sono mai stati creati** e nessun README li usa — ignorali.

## (Ri)registrare il clip hero Analisi (`analisishort.gif`)

Riferimento per quando il clip hero va rifatto (es. dopo un cambio di UI).

**Prima di registrare**
- La finestra ora è **1012×766** (cresciuta di 44 px per la barra di navigazione
  in basso). Avvia l'app e portala in primo piano con uno sfondo pulito dietro.
- Entra in **Play → Analysis / Human Play** così sono visibili **tutte e tre le
  barre**: tool in alto + gruppo struttura a destra, navigazione + annotazione in
  basso.
- In ScreenToGif aggancia la regione di cattura **esattamente alla finestra**
  (Snap to window), **15 fps**.

**Cosa mostrare** (~10-15 s, lento e fluido — è la novità più vistosa):
1. **Hover** su un paio di icone in alto per far apparire il **tooltip** (es.
   🖥️ Engine, 📊 Statistics).
2. Clic su **🖥️ Engine** → parte la valutazione nella striscia sotto la scacchiera.
3. Clic su **📖 Openings** e **📋 PGN** → si aprono i pannelli laterali.
4. Gioca **2-3 mosse** sulla scacchiera.
5. Usa la **barra di navigazione in basso**: **◀ ▶ ⏮ ⏭** (prima/precedente/
   successiva/ultima).
6. (Facoltativo) **❗ Annotate** o **💬 Comment** sull'ultima mossa.

**Esporta e sostituisci**
- Esporta in **GIF** (larghezza ~720, loop infinito) e sovrascrivi
  **`analisishort.gif`** — è l'unico file referenziato dai README, quindi basta
  rifare quello.

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
