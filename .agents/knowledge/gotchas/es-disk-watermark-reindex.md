---
type: Gotcha
title: Reindex scheitert still, wenn die Platte über dem ES-Watermark liegt
description: Ab 85 %/90 % Plattenbelegung verweigert Elasticsearch Shard-Allokation; der neue Index bleibt rot und der Reindex endet mit Timeout statt Plattenhinweis.
tags: [elasticsearch, operations, reindex, disk]
timestamp: 2026-10-21T00:00:00Z
---

# Symptom

`katalon reindex` bzw. der Alias-Rebuild hängt beim Anlegen des neuen Index und endet mit
Timeout; Cluster-Health des neuen Index `red`.

# Ursache

Disk-Watermarks (low 85 %, high 90 %) blockieren die Allokation neuer Shards. Der Full-Rebuild
legt einen frischen Index neben den alten und braucht dafür zusätzlichen Platz.

# Regel

Vor Reindex Platte prüfen (katalon-cli ab 0.3.4 bricht ab 90 % ab). Bei Ausfall Platz schaffen
(alte Images, Backups), nicht die Watermarks hochsetzen.

# Citations

[1] katalon-cli `CHANGELOG.md` 0.3.4; BPK-Server-Vorfall 2026-10-21
[2] [Reindex-Koordination und Streaming](../decisions/reindex-koordination-und-streaming.md)
