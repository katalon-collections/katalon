// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      comment: 'Keine zirkulären Abhängigkeiten im Frontend',
      from: {},
      to: {
        circular: true,
      },
    },
    {
      name: 'types-not-to-impl',
      severity: 'error',
      comment: 'Typdefinitionen dürfen keine Komponenten, Screens oder APIs importieren',
      from: {
        path: '^src/types',
      },
      to: {
        path: '^src/(components|api|hooks|lib)',
      },
    },
    {
      name: 'api-not-to-ui',
      severity: 'error',
      comment: 'API-Clients dürfen keine UI-Komponenten oder Screens importieren',
      from: {
        path: '^src/api',
      },
      to: {
        path: '^src/(components|screens)',
      },
    },
    {
      name: 'ui-primitives-not-to-screens',
      severity: 'error',
      comment: 'UI-Basiskomponenten dürfen keine Screens importieren',
      from: {
        path: '^src/components/ui',
      },
      to: {
        path: '^src/components/screens',
      },
    },
  ],
  options: {
    doNotFollow: {
      path: 'node_modules',
    },
    tsPreCompilationDeps: true,
    tsConfig: {
      fileName: 'tsconfig.json',
    },
  },
};
