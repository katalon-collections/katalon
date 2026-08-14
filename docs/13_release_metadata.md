# Katalon – Release-Metadaten für katalon-cli

**Zielgruppe:** Sysadmins, die Katalon-Deployments über `katalon-cli` installieren, aktualisieren oder zurückrollen. Für das manuelle Docker-Compose-Update ohne `katalon-cli` siehe [Updates und Datenpflege](07_upgrading.md).

## Was ist katalon-cli?

`katalon-cli` ist ein eigenständiges Werkzeug für Installation, Update und Rollback von Katalon-Deployments. Es lebt in einem eigenen Repository, nicht im Haupt-Monorepo. Dieses Repository liefert für jedes getaggte Release lediglich die Metadaten, die `katalon-cli` zur Entscheidungsfindung braucht (Issue #286).

## `katalon-release.json`

Jedes GitHub-Release mit einem Tag `vX.Y.Z` erhält automatisch eine angehängte Datei `katalon-release.json`. Sie wird durch den GitHub-Actions-Workflow `.github/workflows/release-metadata.yml` erzeugt, der `scripts/gen_release_metadata.py` beim Push eines `v*`-Tags ausführt.

Beispielhafte Struktur:

```json
{
  "version": "0.42.0",
  "minimum_installer_version": "0.1.0",
  "migration_required": true,
  "breaking": false,
  "compose_revision": 1,
  "requires": {
    "postgres": ">=16",
    "elasticsearch": ">=8.15,<9"
  }
}
```

| Feld | Herkunft | Bedeutung |
|---|---|---|
| `version` | Git-Tag bzw. `backend/pyproject.toml` | Katalon-Version dieses Releases. |
| `migration_required` | Automatisch ermittelt | `true`, wenn sich seit dem vorherigen Tag Dateien unter `backend/migrations/versions/` geändert haben. Erstes Release: immer `true`. |
| `breaking` | Automatisch ermittelt | `true`, wenn der `CHANGELOG.md`-Abschnitt der Version einen `### Breaking`-Unterabschnitt enthält. |
| `minimum_installer_version` | Manuell in `release-meta.toml` | Mindestversion von `katalon-cli`, die dieses Release installieren kann. Wird hochgezählt, wenn ein Release ein Compose-Template-Feature voraussetzt, das ältere CLI-Versionen nicht kennen. |
| `compose_revision` | Manuell in `release-meta.toml` | Zählt hoch, wenn sich die Service-Topologie (neue Services, andere Ports, anderes Volume-Layout) gegenüber der von `katalon-cli` erwarteten Compose-Struktur ändert. |
| `requires` | Manuell in `release-meta.toml` | Versionsanforderungen an Fremdservices (aktuell PostgreSQL, Elasticsearch). |

## `release-meta.toml`

Die drei manuell gepflegten Felder (`compose_revision`, `minimum_installer_version`, `requires`) liegen in `release-meta.toml` im Repository-Root. Diese Datei nur ändern, wenn sich der jeweilige Sachverhalt tatsächlich ändert — sie wird nicht bei jedem Release automatisch hochgezählt.

## Lokale Erzeugung

Für Tests oder manuelle Releases lässt sich die Datei auch lokal erzeugen:

```bash
python3 scripts/gen_release_metadata.py --tag v0.42.0 --out katalon-release.json
```

Ohne `--tag` verwendet das Skript den exakten Git-Tag des aktuellen `HEAD` (`git describe --tags --exact-match`) und schlägt fehl, wenn `HEAD` keinen Tag trägt.

## Was hier nicht dokumentiert ist

Installation, Update-Ablauf, Rollback-Mechanik und Konfiguration von `katalon-cli` selbst sind Teil des `katalon-cli`-Repositories, nicht dieses Monorepos.
