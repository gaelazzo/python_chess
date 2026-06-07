# Checklist di rilascio (GitHub Release)

Procedura per pubblicare una nuova versione (es. **v1.0.0**). Per i dettagli
del build vedi [BUILD.md](../BUILD.md).

---

## 1. Build dell'eseguibile

Con l'ambiente `env` attivo e `requirements-dev.txt` installato:

```powershell
pyinstaller chessMain.spec --noconfirm --clean
```

Risultato: `dist/chessMain/` (~82 MB) con `chessMain.exe` + `_internal/`.

> Lo `chessMain.spec` è già configurato per includere immagini, splash, dati
> di `pygame_menu`/`pygame_gui` e il driver TTS SAPI5. L'ultima build è
> risultata pulita (nessun warning sui moduli chiave).

## 2. ⚠️ TESTA l'eseguibile (passo obbligatorio)

Il build "riuscito" **non garantisce** che l'app parta: vanno verificati a
runtime i percorsi e i moduli dinamici. Su una macchina (idealmente *senza*
l'ambiente di sviluppo):

```
dist\chessMain\chessMain.exe
```

Controlla che:
- [ ] si apra il menu principale (i pezzi e l'eventuale icona si vedono);
- [ ] **Tools → Setup → Choose engine** trovi Stockfish in `engines\`;
- [ ] **Play vs computer** faccia muovere il motore;
- [ ] **Load (L)** apra un PGN dalla cartella `pgn\`;
- [ ] la sintesi vocale funzioni (o almeno non faccia crashare).

> La finestra di console resta aperta (`console=True`): se qualcosa va storto,
> il traceback è lì.

## 3. Componi il pacchetto da zippare

La radice del pacchetto è il **contenuto** di `dist/chessMain/`. Aggiungi:

- [ ] cartella **`engines/`** (vuota) con dentro un file
      `engines/METTI_QUI_STOCKFISH.txt` — Stockfish **non** è incluso nella
      release (vedi nota sotto);
- [ ] un breve **`LEGGIMI.txt`** / `READ_ME_FIRST.txt` nella radice (testo
      pronto in fondo a questo file);
- [ ] **NON** includere un `config.json` con i tuoi dati personali: l'app ne
      crea uno pulito al primo avvio. Se durante il test (passo 2) ne è stato
      generato uno con le tue impostazioni, **cancellalo** prima di zippare.

Poi comprimi in: **`HiresChess-windows.zip`**.

> **Perché Stockfish non è incluso:** scelta di questa release (zip più
> leggero, nessuna questione di licenza GPL). L'utente lo scarica da
> <https://stockfishchess.org/download/> e lo mette in `engines/`.

## 4. Pubblica su GitHub

> **Ora è automatico.** Un push di un tag `v*` fa partire il workflow
> [.github/workflows/release.yml](../.github/workflows/release.yml), che
> builda Windows + macOS con `release.py` e allega gli asset
> (`HiresChess-windows.zip`, `HiresChess-macos.dmg`) alla release del tag.
> I passi manuali sotto restano come fallback.

`gh` CLI non è installato su questa macchina → due strade.

### 4a. Via web (consigliata)
1. <https://github.com/gaelazzo/python_chess/releases> → **Draft a new release**.
2. **Choose a tag** → digita `v1.0.0` → *Create new tag on publish*.
3. **Release title**: `Hires Chess Trainer v1.0.0`.
4. **Description**: incolla le note pronte (sezione 5).
5. Trascina **`HiresChess-windows.zip`** negli allegati.
6. **Publish release**.

### 4b. Via gh CLI (se preferisci installarlo)
```powershell
winget install GitHub.cli
gh auth login
gh release create v1.0.0 HiresChess-windows.zip `
  --title "Hires Chess Trainer v1.0.0" `
  --notes-file docs/RELEASE_NOTES_v1.0.0.md
```

## 5. Note di rilascio (pronte da incollare — EN)

```markdown
**Hires Chess Trainer v1.0.0** — train on YOUR real chess mistakes.

Import your games from Chess.com/lichess, find where you go wrong (tactics,
openings, endgames) and drill those mistakes with spaced repetition.

### Install (Windows)
1. Download and unzip `HiresChess-windows.zip`.
2. Download Stockfish from https://stockfishchess.org/download/ (AVX2 build)
   and put the `.exe` into the `engines\` folder.
3. Run `chessMain.exe` → Tools → Setup → Choose engine.

Optional: Polyglot opening book (`.bin` in `books\`) and Syzygy tablebases
(set `SyzygyPath` in `config.json`). Full guide: see README / INSTALL.md.

No Python install required. Windows 64-bit.

> macOS: `HiresChess-macos.dmg` is **experimental and currently untested** — use the source / report issues.
```

## 6. Dopo la pubblicazione
- [ ] Verifica che il link in [INSTALL.md](../INSTALL.md) alla pagina Releases
      mostri lo zip.
- [ ] Aggiorna [CHANGELOG.md](../CHANGELOG.md) per la versione successiva.

---

### Testo per `LEGGIMI.txt` (da mettere nello zip)

```
Hires Chess Trainer v1.0.0
==========================

PRIMO AVVIO (3 passi):
1) Scarica Stockfish da https://stockfishchess.org/download/ (versione AVX2)
   e copia il file .exe nella cartella  engines\
2) Avvia  chessMain.exe
3) Menu -> Tools -> Setup -> Choose engine  e seleziona Stockfish.

Opzionali: libro d'apertura .bin in  books\ ; tablebase Syzygy (imposta
SyzygyPath in config.json). Guida completa: https://github.com/gaelazzo/python_chess

Non serve installare Python. Richiede Windows 64-bit.
```
