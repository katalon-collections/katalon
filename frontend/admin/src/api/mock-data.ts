import type { AuditEntry, FieldDefinition, KatalonObject, Vocabulary, VocabularyTerm } from '../types'

export const MOCK_OBJECTS: KatalonObject[] = [
  { id: 'OBJ-2026-00412', idno: 'FOT.1958.0412', object_type: 'fotografie', status: 'public',   metadata_: { title: 'Bahnhofstraße bei Nacht', creator: 'Henri Cartier', year: '1958', medium: 'Silbergelatine' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-30T08:42:00Z' },
  { id: 'OBJ-2026-00411', idno: 'FOT.1972.0118', object_type: 'fotografie', status: 'internal', metadata_: { title: 'Selbstporträt mit Schatten', creator: 'Lina Maier', year: '1972', medium: 'Chromogen-Druck' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-30T06:31:00Z' },
  { id: 'OBJ-2026-00410', idno: 'FOT.1942.0049', object_type: 'fotografie', status: 'draft',    metadata_: { title: 'Werft an der Limmat', creator: 'Unbekannt', year: 'ca. 1942', medium: 'Negativ, Glas' }, created_at: '2026-04-29T09:18:00Z', updated_at: '2026-04-29T09:18:00Z' },
  { id: 'OBJ-2026-00409', idno: 'FOT.1965.0233', object_type: 'fotografie', status: 'public',   metadata_: { title: 'Markttag in der Altstadt', creator: 'G. Albrecht', year: '1965', medium: 'Silbergelatine' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-29T16:51:00Z' },
  { id: 'OBJ-2026-00408', idno: 'FOT.1962.0114', object_type: 'fotografie', status: 'public',   metadata_: { title: 'Kinder am See', creator: 'G. Albrecht', year: '1962', medium: 'Silbergelatine' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-28T14:00:00Z' },
  { id: 'OBJ-2026-00407', idno: 'FOT.1948.0007', object_type: 'fotografie', status: 'internal', metadata_: { title: 'Werkstatt Brunner', creator: 'Hans Brunner', year: '1948', medium: 'Negativ, Glas' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-28T11:00:00Z' },
  { id: 'OBJ-2026-00406', idno: 'FOT.1960.0721', object_type: 'fotografie', status: 'public',   metadata_: { title: 'Tramhaltestelle Paradeplatz', creator: 'Henri Cartier', year: '1960', medium: 'Silbergelatine' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-27T10:00:00Z' },
  { id: 'OBJ-2026-00405', idno: 'FOT.1975.0044', object_type: 'fotografie', status: 'draft',    metadata_: { title: 'Studio-Stillleben mit Geige', creator: 'Lina Maier', year: '1975', medium: 'Chromogen-Druck' }, created_at: '2026-01-10T08:00:00Z', updated_at: '2026-04-27T09:00:00Z' },
]

export const MOCK_FIELDS: FieldDefinition[] = [
  { id: 'f1', target_type: 'object', target_subtype: null, name: 'title',       label: { de: 'Titel',            en: 'Title' },          field_type: 'text',     is_required: true,  is_repeatable: false, is_searchable: true,  sort_order: 0,  settings: {}, show_in_detail: true },
  { id: 'f2', target_type: 'object', target_subtype: null, name: 'alt_titles',  label: { de: 'Weitere Titel',    en: 'Alt. Titles' },    field_type: 'text',     is_required: false, is_repeatable: true,  is_searchable: true,  sort_order: 1,  settings: {}, show_in_detail: true },
  { id: 'f3', target_type: 'object', target_subtype: null, name: 'inventory',   label: { de: 'Inventar-Nr.',     en: 'Inventory No.' },  field_type: 'text',     is_required: true,  is_repeatable: false, is_searchable: true,  sort_order: 2,  settings: {}, show_in_detail: true },
  { id: 'f4', target_type: 'object', target_subtype: null, name: 'creator',     label: { de: 'Urheber:in',       en: 'Creator' },        field_type: 'relation', is_required: false, is_repeatable: true,  is_searchable: false, sort_order: 3,  settings: {}, show_in_detail: true },
  { id: 'f5', target_type: 'object', target_subtype: null, name: 'date',        label: { de: 'Datierung',        en: 'Date' },           field_type: 'date',     is_required: false, is_repeatable: false, is_searchable: true,  sort_order: 4,  settings: {}, show_in_detail: true },
  { id: 'f6', target_type: 'object', target_subtype: null, name: 'medium',      label: { de: 'Material/Technik', en: 'Medium' },         field_type: 'vocab',    is_required: false, is_repeatable: false, is_searchable: true,  sort_order: 5,  settings: { vocabulary: 'photo_medium' }, show_in_detail: true },
  { id: 'f7', target_type: 'object', target_subtype: null, name: 'tags',        label: { de: 'Schlagwörter',     en: 'Tags' },           field_type: 'vocab',    is_required: false, is_repeatable: true,  is_searchable: true,  sort_order: 6,  settings: { vocabulary: 'iconclass' }, show_in_detail: true },
  { id: 'f8', target_type: 'object', target_subtype: null, name: 'rights',      label: { de: 'Rechtevermerk',    en: 'Rights' },         field_type: 'text',     is_required: true,  is_repeatable: false, is_searchable: false, sort_order: 7,  settings: {}, show_in_detail: true },
  { id: 'f9', target_type: 'object', target_subtype: null, name: 'description', label: { de: 'Beschreibung',     en: 'Description' },    field_type: 'richtext', is_required: false, is_repeatable: false, is_searchable: true,  sort_order: 8,  settings: {}, show_in_detail: false },
]

export const MOCK_VOCABS: Vocabulary[] = [
  { id: 'v1', name: 'IconClass',             is_hierarchical: true },
  { id: 'v2', name: 'GND – Personen',        is_hierarchical: false },
  { id: 'v3', name: 'photo_medium (lokal)',  is_hierarchical: false },
  { id: 'v4', name: 'GeoNames – Orte',       is_hierarchical: true },
]

export const MOCK_TERMS: VocabularyTerm[] = [
  { id: 't1', vocabulary_id: 'v3', term: 'Silbergelatine',  label: { de: 'Silbergelatine-Abzug' }, parent_id: null },
  { id: 't2', vocabulary_id: 'v3', term: 'Chromogen-Druck', label: { de: 'Chromogener Farbdruck' }, parent_id: null },
  { id: 't3', vocabulary_id: 'v3', term: 'Negativ, Glas',   label: { de: 'Glasnegativ' },           parent_id: null },
  { id: 't4', vocabulary_id: 'v3', term: 'Cyanotypie',      label: { de: 'Cyanotypie' },            parent_id: null },
]

export const MOCK_AUDIT: AuditEntry[] = [
  { id: 'a1', record_type: 'object', record_id: 'OBJ-2026-00412', record_label: 'FOT.1958.0412', user_id: 'u1', user_name: 'admin@katalon.local', action: 'publish', changed_fields: {}, created_at: '2026-04-30T10:42:00Z' },
  { id: 'a2', record_type: 'object', record_id: 'OBJ-2026-00412', record_label: 'FOT.1958.0412', user_id: 'u1', user_name: 'admin@katalon.local', action: 'update',  changed_fields: { old: { date: '1958' }, new: { date: '1957–1959' } }, created_at: '2026-04-30T10:31:00Z' },
  { id: 'a3', record_type: 'object', record_id: 'OBJ-2026-00410', record_label: 'FOT.1942.0049', user_id: 'u2', user_name: 'editor@katalon.local', action: 'create',  changed_fields: {}, created_at: '2026-04-30T09:18:00Z' },
  { id: 'a4', record_type: 'object', record_id: 'OBJ-2026-00409', record_label: 'FOT.1965.0233', user_id: 'u3', user_name: 'viewer@katalon.local', action: 'update',  changed_fields: { old: { status: 'internal' }, new: { status: 'public' } }, created_at: '2026-04-29T16:51:00Z' },
  { id: 'a5', record_type: 'object', record_id: 'OBJ-2026-00399', record_label: 'FOT.1960.0721', user_id: 'u1', user_name: 'admin@katalon.local', action: 'delete',  changed_fields: {}, created_at: '2026-04-29T14:09:00Z' },
]
