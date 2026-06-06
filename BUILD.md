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

## ⚠️ Prima di buildare: rimuovi l'import morto

Il file [LearningBase.py](LearningBase.py) contiene un `import pgn` (riga 16)
che **non viene usato**: in esecuzione da sorgente "funziona" solo perché
Python risolve la cartella dati `pgn/` come *namespace package*. Nel
pacchetto PyInstaller quella cartella non c'è sul path → l'import fallisce e
**l'eseguibile va in crash all'avvio**.

→ Elimina la riga `import pgn` da `LearningBase.py` prima di buildare
(è innocua: nessun simbolo di `pgn` viene mai usato).

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

## Comporre il pacchetto da distribuire

PyInstaller **non** include i componenti esterni: vanno aggiunti a mano
dentro `dist/chessMain/` prima di zippare.

| Aggiungi | Obbligatorio? | Note |
|---|---|---|
| `engines/stockfish-*.exe` | Sì (per analisi e gioco) | Vedi nota licenza sotto. |
| `books/*.bin` | No | Libro Polyglot, se vuoi farlo giocare su libro. |
| `config.json` di default | Consigliato | Pulito, **senza percorsi personali** (vedi sotto). |

Le cartelle dati (`data/`, `pgn/`, `openings/`, `endgames/`) **non** vanno
incluse: il programma le crea da solo accanto all'eseguibile al primo avvio.

> **Config "pulito".** Il `config.json` versionato contiene i percorsi
> dell'autore (`SyzygyPath`, `reference_db`, `id_student`...). Per la release
> spedisci un `config.json` con quei valori svuotati/neutri, così l'utente
> parte pulito.

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

1. Comprimi `dist/chessMain/` in `HiresChess-windows.zip`.
2. Su GitHub: **Releases → Draft a new release**, crea un tag (es. `v1.0.0`),
   allega lo zip, scrivi due righe di note.
3. Aggiorna il link in [INSTALL.md](INSTALL.md) se necessario.

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
