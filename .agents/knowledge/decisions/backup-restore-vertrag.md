---
type: Decision
title: Backup-Betriebsvertrag — 24h RPO, 30 Tage täglich + 12 Monate monatlich, Offsite-Kopie ist Betreiberaufgabe (Doku, keine Automatisierung)
description: Katalon automatisiert konsistente DB+Medien-Sicherung lokal (backup.sh); Offsite-Kopie, Provider-Wahl und Object-Lock bleiben vollständig manuelle Betreiberaufgabe, dokumentiert mit Beispielbefehlen — kein automatischer S3-Upload im Code, da Katalon kein von uns betriebener Dienst ist (#391).
tags: [operations, backup, restore, betrieb]
timestamp: 2026-09-13T00:00:00Z
---

# Kontext

Production-Readiness-Audit, Abschnitt „Backup und Restore sichern keinen
konsistenten Gesamtzustand“: `docker/backup.sh` erstellt PostgreSQL-Dump und
Medien-Tar sequenziell während Schreibzugriffe weiterlaufen (keine
gemeinsame Konsistenzgrenze), Backups verlassen den Produktivhost nicht
automatisch, es gibt kein Monitoring für Backupalter/-erfolg. Issue #391
verlangt vorab festgelegte RPO/Retention/Offsite-Anforderung.

Eine erste Fassung dieser Entscheidung sah automatisierten S3-Upload direkt
aus `backup.sh` vor (über dieselbe `STORAGE_BACKEND=s3`-Abstraktion wie
Medien). Zurückgestellt: Katalon ist Software, die Institutionen selbst
betreiben, kein von uns zentral betriebener Dienst (siehe
[Tech-Stack](tech-stack.md), „eine Instanz pro Institution“) — welchen
Cloud-Vertrag, Account und Bucket ein Betreiber für sein Offsite-Backup
nutzt, ist dessen eigene Infrastrukturentscheidung, keine, die Katalon ihm
im Code vorwegnehmen sollte.

# Entscheidung

**1. RPO 24h, täglicher Backup-Zyklus.** Kein WAL-Shipping/PITR — das
aktuelle Datenaufkommen rechtfertigt den deutlich höheren Betriebsaufwand
kontinuierlicher Sicherung nicht. Kann bei Bedarf später nachgezogen werden.

**2. Retention: 30 Generationen täglich, danach 12 Monate monatlich.**
Schützt zusätzlich zum reinen Ausfallschutz gegen spät bemerkte
Datenkorruption (z. B. fehlerhafte Migration oder Importfehler, der erst
Wochen später auffällt). `docker/backup.sh` deckt aktuell nur die tägliche
Stufe ab (`BACKUP_RETENTION_DAYS`); die monatliche Langzeitstufe ist
Betreiberaufgabe (z. B. per Offsite-Sync-Policy, siehe Punkt 3).

**3. Offsite-Kopie ist Betreiberaufgabe — Doku, keine Code-Automatisierung.**
`docker/backup.sh` bleibt bei lokalem `pg_dump` + Medien-Tar auf dem
Produktivhost. Eine Offsite-Kopie (zweiter Standort/Account) bleibt
notwendig, damit ein Backup vor Hostverlust schützt — dafür wird **kein**
automatischer Upload-Mechanismus im Code gebaut. `docs/02_produktion.md`
dokumentiert das bereits als Empfehlung (`rsync`/S3 von Hand gegen
`BACKUP_ROOT` spiegeln) und bleibt der einzige Vertrag: Beispielbefehle statt
Code-Pfad, damit jeder Betreiber sein eigenes Ziel/Tooling wählt, ohne dass
Katalon einen Provider oder ein Credential-Handling vorschreibt.

**4. Object-Lock/Immutable-Versioning bleibt reine Betreiber-Empfehlung in
der Doku**, sofern der Betreiber ein S3-kompatibles Offsite-Ziel wählt — kein
Code-seitiger Anspruch, da Katalon diese Offsite-Übertragung gar nicht mehr
selbst ausführt.

**5. Konsistenzgrenze:** DB-Dump und Medien-Snapshot müssen einen definierten
gemeinsamen Zeitpunkt abbilden (z. B. PostgreSQL-Snapshot-Transaktion +
danach unverändertes Medienverzeichnis, oder Dateisystem-/Volume-Snapshot vor
dem Trennen von DB-Dump und Medien-Archivierung) — Umsetzungsdetail, keine
weitere Fachentscheidung nötig.

# Begründung / Scope-Grenzen

- Kein SaaS-Betrieb: Katalon darf Betreibern keine Cloud-Vertrags- oder
  Provider-Entscheidung im Code vorwegnehmen. Ein dokumentierter
  `rsync`/S3-Beispielbefehl lässt jedem Betreiber die Wahl, ohne
  Backup-spezifischen Upload-Code im Repository zu pflegen.
- Der bestehende Restore-Drill (`docs/02_produktion.md`, Abschnitt
  „Restore-Drill“, zuletzt durchgespielt 2026-07-13) deckt DB-Restore,
  Medien-Restore und ES-Reindex bereits ab und bleibt der Nachweis für #391
  — kein separater Offsite-Restore-Test nötig, da Offsite selbst kein
  Katalon-Feature ist.
- Monitoring-/Alerting-Mechanismus für Backup-Alter/-Erfolg ist Teil von
  #396, keine weitere Fachentscheidung hier.

# Citations

- `docs/production-readiness-audit-2026-09-13.md` — Abschnitt „Backup und
  Restore sichern keinen konsistenten Gesamtzustand“
- `docker/backup.sh`
- `docs/02_produktion.md` — Abschnitte „Backups“ und „Restore-Drill“
- GitHub-Issue #391
