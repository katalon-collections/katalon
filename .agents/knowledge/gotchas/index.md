# Gotchas

* [VITE_BASE_PATH](vite-base-path.md) - fehlender Wert bricht Admin-UI still, ohne Build-Fehler
* [click-didyoumean Lock-Pin](click-didyoumean-lock.md) - uv stolpert über inkonsistenten Lock-Eintrag
* [Port-Verwechslung Dev/Prod](port-verwechslung.md) - 3000/3001 vs. 4000/4001 vs. 5173/5174
* [Testsuite braucht KATALON_SECRETS_KEY](pytest-secrets-key.md) - pytest ohne Env-Var → 27 Collection-Errors
* [Public-Repo hat disjunkte Historie](public-repo-disjoint-history.md) - roher Tag-Push an katalon-collections überträgt komplette private Commit-Historie
* [ES nested-Limit bei Relationen](es-nested-limit-relationen.md) - nur ausgehende Relationen indexieren, sonst >10.000 nested-Einträge
* [ES-Watermark beim Reindex](es-disk-watermark-reindex.md) - ab 85/90 % Platte keine Shard-Allokation, Reindex endet mit Timeout
* [Facetten-Label außerhalb der Top-Buckets](facetten-top-buckets-label.md) - ausgewählte Werte immer per `selected`-Subagg mitliefern
