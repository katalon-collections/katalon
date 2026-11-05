---
type: Gotcha
title: Roher Tag-Push an katalon-collections überträgt komplette private Historie
description: origin und katalon-collections/main haben keinen gemeinsamen Vorfahren (publish-open-source.sh squasht). Ein Tag von einem origin-Commit an katalon-collections gepusht schickt alle referenzierten Objekte mit — die gesamte private Commit-Historie landet im public Repo, auch nach Tag-Löschung per SHA fetchbar.
tags: [git, release, security, katalon-collections, tags]
timestamp: 2026-09-03T00:00:00Z
---

# Symptom

`git tag vX.Y.Z <commit-auf-origin-main> && git push katalon-collections vX.Y.Z`
läuft scheinbar sauber durch (`* [new tag] vX.Y.Z -> vX.Y.Z`). Tatsächlich hat Git
dabei aber nicht nur den Tag übertragen, sondern jedes Objekt, das `katalon-collections`
noch nicht kannte — bei fehlendem gemeinsamen Vorfahren ist das die **komplette**
private Commit-Historie (hier: alle 663 Commits seit Projektstart).

# Ursache

`katalon-collections/main` ist keine Fortsetzung von `origin/main`. Es ist eine
eigenständige, über `scripts/publish-open-source.sh` gesquashte Historie
(`git merge-base origin/main katalon-collections/main` liefert nichts — kein
gemeinsamer Vorfahre). Git kennt beim Push nur "welche Objekte hat das Ziel schon",
nicht "gehören die inhaltlich zusammen" — bei disjunkten Historien wird der komplette
Erreichbarkeitsgraph des gepushten Refs übertragen.

Selbst nach `git push katalon-collections :refs/tags/vX.Y.Z` (Tag löschen) bleiben
die Commit-Objekte auf GitHubs Servern für das public Repo per exakter SHA fetchbar
(`git fetch katalon-collections <sha>` funktioniert weiterhin) — GitHub räumt
unreferenzierte Objekte nicht sofort weg.

# Regel

- Release-Tags **immer nur** an `origin` pushen — für jede Version, auch Patches.
- **Niemals** `git tag`/`git push` roh Richtung `katalon-collections`.
- Öffentliche Releases ausschließlich über `scripts/publish-open-source.sh vX.Y.0 <output_dir>`
  erzeugen (Skript lässt nur Minor-Versionen automatisch zu, `PUBLISH_PATCH_RELEASE=1`
  nötig für Patches) und von dort aus veröffentlichen — nie direkt aus dem
  Arbeitsverzeichnis auf `origin`-Basis.
- Bei Verdacht auf versehentlichen Push: Tag sofort löschen (minimiert Referenzierbarkeit),
  danach GitHub-Support für endgültiges Purging der Objekte kontaktieren — Löschen des
  Tags allein reicht nicht.

# Citations

[1] Root `AGENTS.md`, Abschnitt "Repo-Topologie: privat vs. public"
[2] `scripts/publish-open-source.sh`
[3] Vorfall 2026-09-03: `git push katalon-collections v1.19.3` von `origin`-Commit `d283c7e`, sofort per `git push katalon-collections :refs/tags/v1.19.3` zurückgerollt
