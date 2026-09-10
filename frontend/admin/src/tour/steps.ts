// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

export interface TourStep {
  /** Route to navigate to before showing this step (AppShell's hash-route id). */
  route: string
  /** CSS selector for the target element, or 'body' for a centered, non-anchored step. */
  target: string
  title: string
  content: string
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center'
}

export const basicTourSteps: TourStep[] = [
  {
    route: 'list',
    target: 'body',
    placement: 'center',
    title: 'Willkommen bei Katalon',
    content: 'Hier richtest du dein Katalogsystem ein. Wir zeigen dir die wichtigsten Schritte — mit "Ausprobieren" pausierst du und probierst selbst etwas aus, mit "Überspringen" steigst du aus. Die Tour lässt sich später jederzeit erneut starten (Einstellungen → Profil).',
  },
  {
    route: 'subtypes',
    target: '[data-tour="nav-subtypes"]',
    placement: 'right',
    title: 'Subtypen (optional)',
    content: 'Objekte, Entitäten, Orte und Occurrences lassen sich in Subtypen gliedern, z. B. Foto/Gemälde/Dokument bei Objekten. Nicht zwingend — überspringbar, wenn eine flache Struktur reicht.',
  },
  {
    route: 'schema',
    target: '[data-tour="nav-schema"]',
    placement: 'right',
    title: 'Erfassungsmaske anlegen',
    content: 'Hier definierst du Felder für jeden Bestandstyp. Leg ein einfaches Schema an, z. B. Titel + Beschreibung + Datierung.',
  },
  {
    route: 'schema',
    target: '[data-tour="field-type-select"]',
    placement: 'left',
    title: 'Spezialfelder',
    content: 'Neben Text gibt es Vokabular-, Relations-, Autoritäts- und Geo-Felder. Öffne ein Feld zum Bearbeiten und schau dir das Feldtyp-Dropdown an — nicht jetzt konfigurieren nötig.',
  },
  {
    route: 'vocab',
    target: '[data-tour="nav-vocab"]',
    placement: 'right',
    title: 'Erstes Vokabular',
    content: 'Vokabulare sind kontrollierte Wertelisten (z. B. Materialtypen). Leg eins mit 2-3 Begriffen an.',
  },
  {
    route: 'vocab',
    target: '[data-tour="nav-vocab"]',
    placement: 'right',
    title: 'Relationstypen festlegen',
    content: 'Relationstypen (z. B. "abgebildet in", "Teil von") sind ebenfalls ein Vokabular — das Vokabular "relation_types" — optional mit Typ-Paar-Beschränkungen je Kombination.',
  },
  {
    route: 'list',
    target: '[data-tour="new-record-button"]',
    placement: 'bottom',
    title: 'Erstes Objekt anlegen',
    content: 'Leg dein erstes Objekt mit der eben gebauten Maske an und speichere es.',
  },
  {
    route: 'form',
    target: '[data-tour="relations-section"]',
    placement: 'left',
    title: 'Verknüpfen',
    content: 'Verknüpfe das Objekt mit einer Entität, einem Ort oder einer Occurrence — z. B. den Fotografen als Entität.',
  },
  {
    route: 'form',
    target: '[data-tour="media-section"]',
    placement: 'left',
    title: 'Medien hochladen',
    content: 'Lade ein Bild oder Dokument hoch. Es wird automatisch für IIIF aufbereitet.',
  },
  {
    route: 'form',
    target: '[data-tour="record-status"]',
    placement: 'bottom',
    title: 'Präsentationsschicht',
    content: 'Steuere hier die Sichtbarkeit: Entwurf, Intern oder Öffentlich. Erst "Öffentlich" erscheint im Portal.',
  },
  {
    route: 'oai-sets',
    target: '[data-tour="nav-oai-sets"]',
    placement: 'right',
    title: 'Erstes OAI-PMH-Set',
    content: 'Für Datenaustausch definierst du hier Sets, z. B. alle Objekte eines Subtyps. Optional, nur bei Bedarf.',
  },
  {
    route: 'oai-sets',
    target: 'body',
    placement: 'center',
    title: 'Das war\'s für den Einstieg',
    content: 'Mehr sehen? Die erweiterte Tour zeigt Importer, Normdaten, vererbte Felder, Vorgänge und mehr. Jederzeit über das Hilfe-Icon im Header erneut startbar.',
  },
]

export const advancedTourSteps: TourStep[] = [
  {
    route: 'form-variants',
    target: '[data-tour="nav-form-variants"]',
    placement: 'right',
    title: 'Formularvarianten',
    content: 'Mehrere Erfassungsmasken pro Subtyp — z. B. Kurz- vs. Vollerfassung.',
  },
  {
    route: 'import',
    target: '[data-tour="nav-import"]',
    placement: 'right',
    title: 'Smart Importer',
    content: 'Massenimport aus Excel/CSV/XML mit Dry-Run und Feld-Mapping.',
  },
  {
    route: 'schema',
    target: '[data-tour="nav-schema"]',
    placement: 'right',
    title: 'Normdaten-Anbindung',
    content: 'GND/Geonames als Feldtyp "Normdaten (Authority)" im Schema-Editor einbinden — Autovervollständigung bei Entitäten und Orten.',
  },
  {
    route: 'schema',
    target: '[data-tour="nav-schema"]',
    placement: 'right',
    title: 'Vererbte Felder',
    content: 'Felder aus verknüpften Datensätzen lassen sich in den Suchindex übernehmen (z. B. Ortsname bei einem Objekt mit Ortsbezug).',
  },
  {
    route: 'procedures-list',
    target: '[data-tour="nav-procedures-list"]',
    placement: 'right',
    title: 'Vorgänge',
    content: 'Leihverkehr, Erwerbung und Restaurierung als eigener Bestandstyp mit Workflow-Charakter.',
  },
  {
    route: 'users',
    target: '[data-tour="nav-users"]',
    placement: 'right',
    title: 'Rollen & Rechte',
    content: 'Weitere Benutzer anlegen, Rollen (Admin/Editor/Viewer) zuweisen.',
  },
  {
    route: 'audit',
    target: '[data-tour="nav-audit"]',
    placement: 'right',
    title: 'Audit-Log',
    content: 'Jede Änderung wird protokolliert — nachvollziehbar wer, wann, was geändert hat.',
  },
  {
    route: 'pages',
    target: '[data-tour="nav-pages"]',
    placement: 'right',
    title: 'Portal-Inhalte',
    content: 'Statische Seiten und Banner fürs Public-Portal pflegen.',
  },
]
