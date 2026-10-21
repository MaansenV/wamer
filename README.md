# wamer

Wärmt die rollierenden ~5h-Usage-Windows von **Claude Code** (Pro/Max-Sub) — per kostenlosem GitHub-Actions-Cron.
Kein Laptop nötig, keine API-Keys, kein Extra-Billing.

**Keine lückenlose Garantie:** GitHub kann Cron-Läufe verzögern oder auslassen.
Alle 10 Minuten sind geplant; beobachtet wurden trotzdem mehrstündige Lücken.
Für garantierte Zeitplanung ist ein externer Zeitgeber nötig.

Fork-Adaption von [viseshb/claude-codex-warmer](https://github.com/viseshb/claude-codex-warmer) (MIT).

## Wie es funktioniert

Ein Workflow (`.github/workflows/warm.yml`), drei Jobs:

| Job | Funktion |
|-----|----------|
| `warm-claude` | Sendet `"hi"` an `claude-haiku-4-5` via OAuth-Token — aber nur bei kaltem Fenster |
| `notify` | Bei Fail: Issue „Warm-up needs attention" mit Fix-Kommandos (→ E-Mail); Auto-Close nur nach echtem erfolgreichem Claude-Send |
| `heartbeat` | 1 Commit/Tag, damit GitHub den Schedule nie wegen 60 Tagen Inaktivität deaktiviert |

Jeder Trigger fragt zuerst das **account-eigene Live-Meter**: Fenster aktiv (egal von
welchem Gerät gestartet) → Skip. Kalt → ein `"hi"`, das ein frisches Fenster startet.
Fallback bei unerreichbarem Meter: `.state/claude-last-warm.txt` mit 5h01m-Schwelle.
Manueller Run (**Actions → warm-usage-windows → Run workflow**) sendet immer echt.

Kosten: ~5 Sends/Tag à ~4,5k Tokens (fast alles CLI-System-Prompt),
Bruchteil eines Prozents des Fenster-Budgets.

## Abweichungen zum Upstream

- **Public Repo:** Cron alle 10 Min (`7,17,27,37,47,57 * * * *`).
  Secrets bleiben verschlüsselt; der Workflow
  hat keine PR-Trigger, Fork-PRs sehen nie Secrets. Regel: keine Workflow-Änderungen
  aus fremden PRs mergen. Externe Actions sind per Commit-SHA gepinnt (Supply-Chain-Härtung).
- Commit-Timestamps in `Europe/Berlin` (nur Kosmetik).
- Nur Claude; Codex-Warming entfernt.

## Setup

### 0. Voraussetzungen

- Claude **Pro/Max**-Sub
- Lokal: `claude`-CLI + `gh` (GitHub CLI, eingeloggt)

### 1. Secrets setzen (⚠️ NUR interaktiv in deinem Terminal!)

Browser-OAuth hängt in Agent-Shells/CI — diese Befehle musst **du von Hand** ausführen.
Vorher prüfen: CLI ist in **demselben Account** eingeloggt, den deine Apps nutzen
(häufigster Fehler überhaupt: falscher Account → grüne Runs, kaltes Fenster).

```bash
# Claude: öffnet Browser, richtigen Account wählen
claude setup-token
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo MaansenV/wamer
# ... sk-ant-oat... Token einfügen
```

| Secret | Pflicht? | Notizen |
|--------|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | ja | Von `claude setup-token`, ~1 Jahr gültig |

### 2. Testen

```bash
gh workflow run warm.yml --repo MaansenV/wamer
gh run watch --repo MaansenV/wamer
```

Manuelle Runs versuchen immer einen echten Send. Grün bestätigt erfolgreiche Requests, aber noch nicht Account-Identität oder Fenster-Registrierung.
Geplante grüne Skip-Läufe beweisen weder einen Send noch behobene Authentifizierung.

### 3. Verifizieren (Pflicht!)

Am nächsten Morgen Claude öffnen, **bevor** du tippst: Eine Session bei 0%
mit Reset-Zeit ≠ jetzt+5h muss schon laufen. Sonst: Account/Modell prüfen —
ein grüner Run allein beweist nichts.

Canary im Log: Dauerhaft „no active window" trotz kürzlich erfolgreicher Sends = Sends registrieren nicht
(Modell zahlt nicht aufs Meter ein, oder falscher Account).

## Konfiguration

- **Intervall:** Cron in `warm.yml` (alle 10 Min; GitHub bleibt best-effort).
  `WARM_INTERVAL_SECONDS` (5h01m) und `MIN_REWARM_SECONDS` (1h Safety-Floor) nur
  anfassen, wenn du weißt warum.
- **CLI-Pins:** `CLAUDE_CLI_VERSION` in `warm.yml` (Upstream-verifiziert).
  Bump nur bewusst + danach manueller Testlauf.
- **Modelle:** Nur wechseln mit anschließender Reset-Zeit-Verifikation — Mini-Modelle
  zählen tlw. in separaten Bucket und starten **kein** Fenster!

## Troubleshooting

- **Grün, aber nie warm:** falscher Account beim Token-Minting (Re-Mint im richtigen
  Account) oder Modell ohne Meter-Registrierung.
- **Claude „organization has disabled ... subscription access":** Abozugriff für
  Claude Code in der Organisation aktivieren oder Token im richtigen Abo-Account
  erstellen; das ist nicht automatisch ein abgelaufenes Token.
- **Claude Live-Meter unavailable:** Fallback auf den letzten Send; dessen
  Zeitstempel belegt keinen laufenden Usage-Bucket.

## Regressionstests

```powershell
python -m unittest discover -s tests -v
```

Python-Standardbibliothek; für die Shell-Tests zusätzlich Bash (Windows: Git for Windows).

## Sicherheit

- Keine Keys im Repo — Auth nur in verschlüsselten Actions-Secrets (GitHub maskiert sie in Logs).
- `.gitignore` blockt `auth.json`/`.env`/PEM-Dateien.
- Externe Actions sind auf volle Commit-SHAs gepinnt; keine PR-Trigger → Forks sehen nie Secrets.
- Empfohlen: Ruleset gegen Force-Push/Branch-Deletion (Settings → Rules).

## Lizenz

[MIT](LICENSE) — Fork-Adaption von viseshb/claude-codex-warmer (MIT).
