# Installazione — Hires Chess Trainer

🇬🇧 *English version: coming soon*

Ci sono due modi per installare il programma, a seconda di chi sei:

- **[A) Sei un giocatore](#a-utente-finale--eseguibile-pronto)** — vuoi solo
  usarlo, senza installare Python. → Scarica l'eseguibile.
- **[B) Sei uno sviluppatore](#b-da-sorgente-sviluppatori--utenti-avanzati)**
  — vuoi i sorgenti, modificarli o contribuire. → Installa da sorgente.

In **entrambi i casi** serve un motore di scacchi esterno (Stockfish): vedi
[Configurazione iniziale](#configurazione-iniziale-comune-a-tutti).

---

## A) Utente finale — eseguibile pronto

> ⚠️ Al momento l'eseguibile precompilato potrebbe non essere ancora
> pubblicato tra le *Release*. Se la pagina Release è vuota, usa il
> percorso **B (da sorgente)** oppure chiedi all'autore una build.
> Per produrre l'eseguibile vedi [BUILD.md](BUILD.md).

1. Vai su **[Releases](https://github.com/gaelazzo/python_chess/releases)**
   e scarica l'ultimo file `HiresChess-windows.zip`.
2. **Estrai** lo zip in una cartella a tua scelta (es. `C:\HiresChess`).
   Non serve installare Python.
3. Procurati **Stockfish** (vedi [sotto](#1-motore-stockfish-obbligatorio))
   e mettilo nella sottocartella `engines\`.
4. Avvia **`chessMain.exe`** (doppio clic).
5. Al primo avvio: **Tools → Setup → Choose engine** e seleziona il file di
   Stockfish.

---

## B) Da sorgente (sviluppatori / utenti avanzati)

### Prerequisiti
- **Python 3.10 o superiore** (sviluppato e testato su 3.13) —
  [python.org/downloads](https://www.python.org/downloads/).
  In fase di installazione spunta *"Add Python to PATH"*.
- **Git** (per clonare) — oppure scarica lo zip del repo da GitHub.

### Passi

```powershell
# 1. Clona il repository
git clone https://github.com/gaelazzo/python_chess.git
cd python_chess

# 2. Crea l'ambiente virtuale (chiamalo "env" cosi' funziona anche run chess.bat)
python -m venv env

# 3. Attiva l'ambiente
#    PowerShell:
.\env\Scripts\Activate.ps1
#    Prompt dei comandi (cmd):
#    .\env\Scripts\activate.bat

# 4. Installa le dipendenze
pip install -r requirements.txt
```

> Se PowerShell blocca l'attivazione con un errore di *execution policy*,
> esegui una volta:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.

### Avvio
Tre modi equivalenti:
- doppio clic su **`run chess.bat`** (attiva `env` e lancia il programma);
- da terminale con l'env attivo: **`python chessMain.py`**;
- da **VS Code**: apri la cartella e premi **F5** (config *"Run Chess"* già
  inclusa in `.vscode/launch.json`).

---

## Configurazione iniziale (comune a tutti)

### 1. Motore Stockfish (obbligatorio)
Senza un motore UCI **non funzionano** l'analisi né il gioco contro il
computer.

1. Scarica Stockfish da
   **[stockfishchess.org/download](https://stockfishchess.org/download/)**
   (per PC moderni scegli la build *AVX2*).
2. Copia l'eseguibile (es. `stockfish-windows-x86-64-avx2.exe`) nella
   cartella **`engines\`** del programma.
3. Avvia il programma → **Tools → Setup → Choose engine** → seleziona il
   file. La scelta viene salvata in `config.json` (chiave `engine`).

### 2. Libro d'apertura Polyglot (facoltativo)
Per far giocare il computer "su libro": metti un file `.bin` (formato **Polyglot**)
nella cartella **`books\`**, poi **Tools → Setup → Choose book**.

Il programma **non** include un libro: scaricane uno gratuito. Alcune fonti:

- **donna_opening_books** — <https://github.com/michaeldv/donna_opening_books>
  (`gm2001.bin`: partite 2001–2013 con Elo ≥ 2530; `komodo.bin`; `rodent.bin`).
- **free-opening-books** — <https://github.com/gmcheems-org/free-opening-books>
  (raccolta più ampia: `gm2001.bin`, `komodo.bin`, `rodent.bin`, `Titans.bin`,
  `Human.bin`, Cerebellum, …).

Su GitHub: apri il file `.bin` → **Download raw file**, poi copialo in `books\`.
Sono libri distribuiti dalla community: le licenze non sono sempre esplicite,
verificale prima di **ridistribuirli**. Chi ha ChessBase/Fritz può anche esportare
un proprio libro in formato Polyglot.

### 3. Syzygy tablebase (facoltativo, per i finali)
Per il giudizio perfetto dei finali (≤ 7 pezzi):
1. Scarica le tablebase Syzygy (3-4-5 pezzi bastano per iniziare; 6-7 pezzi
   pesano molti GB).
2. In `config.json`, sotto `engine_options`, imposta `SyzygyPath` con i
   percorsi separati da **`;`** (es.
   `"D:\\TB\\345;D:\\TB\\6"`).
3. Verifica con:
   ```
   python verify_syzygy.py
   python verify_stockfish_tb.py
   ```

### 4. BrainMaster (facoltativo, lezioni assistite)
Solo se usi il servizio AI esterno: imposta `base_url` e `id_student` in
`config.json` (o da **Tools → Setup**).

> **Nota sul `config.json`.** Il file versionato contiene le impostazioni
> dell'autore (percorsi personali, username): è normale. Le tue scelte fatte
> da **Tools → Setup** lo riscrivono con i tuoi valori al primo utilizzo.

---

## Risoluzione problemi

| Sintomo | Causa / Soluzione |
|---|---|
| `ModuleNotFoundError: No module named 'pygame'` (o altro) | L'ambiente virtuale non è attivo, oppure mancano le dipendenze. Attiva `env` e ri-esegui `pip install -r requirements.txt`. |
| `pip install` fallisce | Aggiorna pip: `python -m pip install --upgrade pip`, poi riprova. Verifica di avere Python 3.10+. |
| L'analisi / "Play vs computer" non parte | Stockfish non configurato: **Tools → Setup → Choose engine**. |
| Finali sempre giudicati con l'engine, mai con la TB | `SyzygyPath` errato: controlla i percorsi e lancia `python verify_stockfish_tb.py`. |
| Nessuna voce / errore TTS all'avvio | La sintesi vocale usa le voci di Windows (SAPI5). Imposta una voce valida in `config.json` → `tts_voice`, o lasciala vuota. |
| La finestra non si apre / crash grafico | Aggiorna i driver video ed esegui in una sessione desktop reale (non headless / RDP limitato). |

---

📖 Per l'uso del programma una volta installato, vedi il manuale:
[README.md](README.md) (EN) · [README.it.md](README.it.md) (IT).
🔧 Per **produrre** l'eseguibile distribuibile, vedi [BUILD.md](BUILD.md).
