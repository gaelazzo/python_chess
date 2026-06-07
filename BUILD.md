# Build — pacchetti distribuibili Windows/macOS

Come trasformare i sorgenti in un pacchetto che gli utenti possono lanciare
**senza installare Python**. Su Windows viene generato
`HiresChess-windows.zip`; su macOS viene generato `HiresChess-macos.dmg` con
`HiresChess.app`. Si usa
[PyInstaller](https://pyinstaller.org/) con lo spec già presente nel repo
([chessMain.spec](chessMain.spec)).

---

## Prerequisiti

1. Aver completato l'installazione **da sorgente** (vedi
   [INSTALL.md](INSTALL.md) sezione B) con l'ambiente `env` attivo.
   Su macOS usa Python 3.12 o 3.13 per la release: con Python 3.14 `pygame`
   puo' non avere wheel disponibili e provare a compilare SDL da sorgente.
2. Installare gli strumenti di build:
   ```powershell
   pip install -r requirements-dev.txt
   ```
   (include `pyinstaller`; opzionale: [UPX](https://upx.github.io/) nel PATH
   per comprimere i binari — lo spec ha `upx=True`, se UPX manca viene solo
   ignorato).

---

## Build

Con l'ambiente attivo, dalla cartella del progetto:

```bash
python release.py
```

Lo script controlla prima che le dipendenze runtime (`pygame`, `pygame_menu`,
`pygame_gui`, ecc.) siano installate nell'ambiente attivo: se mancano, si
ferma prima di creare un pacchetto rotto.

Per fermarti dopo il build PyInstaller, senza creare zip/DMG:

```bash
python release.py --build-only
```

Risultato Windows (modalità *onedir*):

```
dist/
└── chessMain/
    ├── chessMain.exe        <- l'eseguibile
    └── _internal/           <- librerie, Python embedded, immagini
```

Lo spec impacchetta automaticamente le immagini dei pezzi (`images/*.png`) e
lo splash (`pic-chess.png`).

Risultato macOS:

```
dist/
└── HiresChess.app/
    └── Contents/
```

---

## Cosa contiene il pacchetto

`python release.py` produce `dist/HiresChess-windows.zip` **già pronto**:
dentro una cartella `HiresChess/` ci sono l'eseguibile, le sue librerie
(`_internal/`), un `config.json` pulito, un `LEGGIMI.txt`, e le cartelle utente
`engines/ books/ data/ pgn/ openings/ endgames/` — ognuna con il proprio
README/nota (copiati dal repo da `stage_user_folders` in `release.py`). Non
devi aggiungere nulla a mano.

**Stockfish NON è incluso** (scelta: zip più leggero, nessuna questione di
licenza GPL): l'utente lo scarica e lo mette in `engines/` seguendo il
`LEGGIMI.txt` (vedi anche [INSTALL.md](INSTALL.md)). Se in futuro volessi
includerlo, ricorda la licenza GPLv3 (vedi sotto).

### Licenza di Stockfish (importante)
Stockfish è **GPLv3**, questa app è MIT. Lo chiami come processo separato
(UCI), quindi il tuo codice resta MIT. Ma se **distribuisci il binario** di
Stockfish nel pacchetto devi rispettare la GPLv3:
- includi il testo della licenza accanto al binario (es.
  `engines/Stockfish-LICENSE.txt`);
- indica dove trovare i sorgenti:
  <https://github.com/official-stockfish/Stockfish>.

In alternativa **non** impacchettare Stockfish e fai scaricare/scegliere il
motore all'utente al primo avvio (vedi INSTALL.md).

---

## Distribuzione

Due strade:

**A) Automatica (consigliata).** Fai push di un tag `v*`
(`git tag v1.1.0 && git push origin v1.1.0`): il workflow
[.github/workflows/release.yml](.github/workflows/release.yml) builda Windows +
macOS con `release.py` e pubblica la release con gli asset allegati.

**B) Manuale.** `python release.py` crea `dist/HiresChess-windows.zip`; poi su
GitHub **Releases → Draft a new release**, crea il tag, allega lo zip e
pubblica. Vedi anche [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

---

## Risoluzione problemi build

| Sintomo | Soluzione |
|---|---|
| L'exe si chiude subito | Lascia `console=True` nello spec (già impostato) per leggere il traceback; quasi sempre è l'`import pgn` non rimosso o un `engines/` mancante. |
| `Failed to execute script chessMain` | Dipendenza non rilevata: aggiungila a `hiddenimports` in `chessMain.spec`. |
| Immagini dei pezzi mancanti | Controlla la sezione `datas` in `chessMain.spec` e che `images/*.png` esista. |
| Antivirus segnala l'exe | Falso positivo comune con PyInstaller; firma il binario o documenta l'eccezione. |

> **Android (sperimentale).** Esiste un [buildozer.spec](buildozer.spec) per
> un eventuale port mobile, ma non è un percorso supportato/testato: questo
> documento copre solo la build Windows.
