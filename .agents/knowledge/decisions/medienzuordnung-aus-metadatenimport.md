---
type: Decision
title: Medienzuordnung aus dem Metadatenimport
description: Ein nutzergewählter Quell-Selector speichert offene Dateireferenzen je Objekt; der spätere Batch-Medienimport löst sie anhand normalisierter Dateinamen auf.
tags: [importer, medien, datenmodell, batch-import]
timestamp: 2026-08-20T00:00:00+02:00
---

# Kontext

Metadatenexporte können Bilddateinamen enthalten, während die Dateien getrennt
als Ordner oder ZIP-Archiv vorliegen. Der bisherige Medienimport verlangte dafür
entweder interne Objekt-UUIDs in Ordner- oder Dateinamen oder eine zusätzliche
CSV-Datei mit Dateiname und Objekt-ID. Die Quelldaten enthielten die fachliche
Zuordnung bereits, der Metadatenimport verwarf sie aber nach dem Anlegen oder
Zuordnen des Objekts.

Die XML-Importer-Architektur ist formatagnostisch. Eine feste Auswertung von
LIDO-Elementen hätte dieser Entscheidung widersprochen und andere XML- oder
Tabellenformate ausgeschlossen.

# Entscheidung

Der Objektimport bietet eine optionale Medienzuordnung. Der Nutzer wählt eine
CSV-/Excel-Spalte oder einen XML-Selector mit Dateinamen. Der Selector bleibt
getrennt vom Metadaten-Mapping und wird nicht in `Object.metadata_` geschrieben.

Der Importtask speichert die Werte als `MediaImportReference` mit Objekt-ID,
Originaldateiname und normalisiertem Basename. Die Kombination aus Objekt-ID
und normalisiertem Dateinamen ist eindeutig. Wiederholte Importe verwenden
`ON CONFLICT DO NOTHING`. Bei bestehenden Objekten ergänzt auch die
Upsert-Strategie `skip` fehlende Medienreferenzen, ohne die Metadaten zu ändern.

Der Batch-Medienimport wertet explizite CSV-Zuordnungen zuerst aus. Für übrige
Dateien sucht er offene Medienreferenzen und verwendet danach den bestehenden
UUID-Fallback. Verweist ein normalisierter Dateiname auf mehrere Objekte, wird
keines davon automatisch gewählt. Nach erfolgreicher Anlage der `MediaFile`-Zeile
wird die passende Referenz in derselben Datenbanktransaktion gelöscht; bei einem
Fehler bleibt sie für einen späteren Versuch bestehen.

# Begründung

Ein eigener technischer Referenztyp hält Importzustand aus den konfigurierbaren
Objektmetadaten heraus und überlebt die getrennten Celery-Tasks für Metadaten und
Bilder. Der nutzergewählte Selector erhält die generische Importarchitektur. Die
Priorität von CSV, gespeicherter Referenz und UUID-Fallback bewahrt bestehende
Importwege, während neue Importe keine manuell erzeugte Mapping-Datei mehr
benötigen.

Die Normalisierung auf Basename, Unicode NFC und Groß-/Kleinschreibung entspricht
dem Dateivergleich des Batch-Imports. Konflikte werden gemeldet, weil eine
willkürliche Zuordnung Bilder am falschen Objekt ablegen könnte.

# Citations

[1] `backend/src/katalon/api/v1/importer.py`
[2] `backend/src/katalon/services/media_batch_import_service.py`
[3] `backend/src/katalon/workers/import_tasks.py`
[4] `backend/src/katalon/workers/media_tasks.py`
[5] `backend/src/katalon/core/models.py`
[6] `backend/migrations/versions/0038_media_import_references.py`
[7] `frontend/admin/src/components/screens/importer/StepMapping.tsx`
[8] `.agents/knowledge/decisions/xml-importer-scope.md`
