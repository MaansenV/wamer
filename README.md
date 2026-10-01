# wamer

Hält die rollierenden ~5h-Usage-Windows von **Claude Code** (Pro/Max-Sub) und
**Codex** (ChatGPT-Sub) rund um die Uhr warm — per kostenlosem GitHub-Actions-Cron.
Kein Laptop nötig, keine API-Keys, kein Extra-Billing.

Fork-Adaption von [viseshb/claude-codex-warmer](https://github.com/viseshb/claude-codex-warmer) (MIT).

## Wie es funktioniert

Ein Workflow (`.github/workflows/warm.yml`), vier Jobs:

| Job | Funktion |
|-----|----------|
| `warm-claude` | Sendet `"hi"` an `claude-haiku-4-5` via OAuth-Token — aber nur bei kaltem Fenster |
| `warm-codex` | Sendet `"hi"` an `gpt-5.6-sol` (low reasoning) via restored `auth.json`; schreibt rotierte Tokens per `GH_PAT` ins Secret zurück |
| `notify` | Bei echtem Fail: Issue „Warm-up needs attention" mit Fix-Kommandos (→ E-Mail), Auto-Close bei Erfolg |
| `heartbeat` | 1 Commit/Tag, damit GitHub den Schedule nie wegen 60 Tagen Inaktivität deaktiviert |

Jeder Trigger fragt zuerst das **account-eigene Live-Meter**: Fenster aktiv (egal von
welchem Gerät gestartet) → Skip. Kalt → ein `"hi"`, das ein frisches Fenster startet.
Fallback bei unerreichbarem Meter: `.state/*-last-warm.txt` mit 5h01m-Schwelle.
Manueller Run (**Actions → warm-usage-windows → Run workflow**) sendet immer echt.

Kosten: ~5 Sends/Provider/Tag à ~4,5k Tokens (fast alles CLI-System-Prompt),
Bruchteil eines Prozents des Fenster-Budgets.

## Abweichungen zum Upstream (privates Repo!)

- **Cron alle 2 Stunden** (`7 */2 * * *`) statt alle 30 Min — Minuten-Rechnung:
  ein Trigger kostet ~3,5 Min über alle Jobs; 48 Trigger/Tag wären ~5.000 Min/Monat,
  Free-Tier für private Repos sind 2.000. Mit 12 Triggern/Tag landen wir bei
  ~1.300 Min/Monat ✅. Trade-off: nach Fenster-Ablauf im Schnitt ~1h Lücke.
  Bei GitHub Pro oder public Repo gern zurück auf `7,37 * * * *` stellen.
- **Codex: 1× `codex login`** (Upstream-Stand aus `warm.yml`, verifiziert 2026-08-14):
  ein 2. Login revoked das hochgeladene Token (`token_revoked`). `GH_PAT` für
  Write-back ist dadurch Pflicht für Dauerbetrieb.
- Commit-Timestamps in `Europe/Berlin` (nur Kosmetik).

## Setup

### 0. Voraussetzungen

- Claude **Pro/Max**-Sub und/oder ChatGPT-Sub mit **Codex**-Zugang
- Lokal: `claude`-/`codex`-CLI + `gh` (GitHub CLI, eingeloggt)

### 1. Secrets setzen (⚠️ NUR interaktiv in deinem Terminal!)

Browser-OAuth hängt in Agent-Shells/CI — diese Befehle musst **du von Hand** ausführen.
Vorher prüfen: CLI ist in **demselben Account** eingeloggt, den deine Apps nutzen
(häufigster Fehler überhaupt: falscher Account → grüne Runs, kaltes Fenster).

```bash
# Claude: öffnet Browser, richtigen Account wählen
claude setup-token
gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo MaansenV/wamer
# ... sk-ant-oat... Token einfügen

# Codex: EINMAL einloggen, hochladen, danach in Ruhe lassen!
codex login
gh secret set CODEX_AUTH_JSON --repo MaansenV/wamer < ~/.codex/auth.json
```

PowerShell-Variante für Codex (kein `<`-Redirect):

```powershell
Get-Content -Raw "$env:USERPROFILE\.codex\auth.json" | gh secret set CODEX_AUTH_JSON --repo MaansenV/wamer
```

| Secret | Pflicht? | Notizen |
|--------|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | für Claude | Von `claude setup-token`, ~1 Jahr gültig |
| `CODEX_AUTH_JSON` | für Codex | Inhalt von `~/.codex/auth.json` nach `codex login`. Danach lokal **nicht** erneut einloggen — das revoked CI (`token_revoked`)! |
| `GH_PAT` | de-facto ja | Fine-grained PAT mit **Secrets: read/write** auf dieses Repo → Write-back rotierter Tokens, sonst stirbt Codex-Login nach ~30h |

### 2. Testen

```bash
gh workflow run warm.yml --repo MaansenV/wamer
gh run watch --repo MaansenV/wamer
```

Manuelle Runs senden immer echt. Grüne Jobs = beide Fenster laufen gerade.

### 3. Verifizieren (Pflicht!)

Am nächsten Morgen Claude/Codex öffnen, **bevor** du tippst: Eine Session bei 0%
mit Reset-Zeit ≠ jetzt+5h muss schon laufen. Sonst: Account/Modell prüfen —
ein grüner Run allein beweist nichts.

Canary im Log: Dauerhaft „no active window" alle 2h = Sends registrieren nicht
(Modell zahlt nicht aufs Meter ein, oder falscher Account).

## Konfiguration

- **Intervall:** Cron in `warm.yml` (aktuell 2h, siehe Minuten-Rechnung oben).
  `WARM_INTERVAL_SECONDS` (5h01m) und `MIN_REWARM_SECONDS` (1h Safety-Floor) nur
  anfassen, wenn du weißt warum.
- **CLI-Pins:** `CLAUDE_CLI_VERSION` / `CODEX_CLI_VERSION` in `warm.yml` (Upstream-verifiziert).
  Bump nur bewusst + danach manueller Testlauf.
- **Modelle:** Nur wechseln mit anschließender Reset-Zeit-Verifikation — Mini-Modelle
  zählen tlw. in separaten Bucket und starten **kein** Fenster!

## Troubleshooting

- **Grün, aber nie warm:** falscher Account beim Token-Minting (Re-Mint im richtigen
  Account) oder Modell ohne Meter-Registrierung.
- **Codex 401s:** Refresh-Token tot (kein Write-back ohne `GH_PAT`, oder lokale
  Parallelnutzung hat die Token-Familie rotiert) → Fix-Kommandos stehen im Auto-Issue.
- **Minuten aufgebraucht:** Cron weiter ausdünnen oder Repo auf public stellen.

## Sicherheit

- Keine Keys im Repo — Auth nur in verschlüsselten Actions-Secrets (GitHub maskiert sie in Logs).
- `.gitignore` blockt `auth.json`/`.env`/PEM-Dateien.
- Empfohlen: Ruleset gegen Force-Push/Branch-Deletion (Settings → Rules).

## Lizenz

[MIT](LICENSE) — Fork-Adaption von viseshb/claude-codex-warmer (MIT).
