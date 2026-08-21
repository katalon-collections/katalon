import type { ReactNode } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'
import { authorityUrl, pidUrl, renderFieldValue } from '../utils/renderFieldValue'
import { RelationFieldRow } from './RelationFieldRow'

export function MetaRow({ label, value, href }: { label: string; value: string; href?: string }) {
  if (!value) return null
  return (
    <div className="meta-row">
      <span className="key">{label}</span>
      <span className="val">
        {href ? <a href={href} target="_blank" rel="noreferrer">{value}</a> : value}
      </span>
    </div>
  )
}

function fieldLabel(f: FieldDefinition, locale: string): string {
  return f.label?.[locale] ?? f.label?.de ?? f.label?.en ?? f.name
}

function richText(value: string): ReactNode {
  return (
    <div className="prose" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(value) as string) }} />
  )
}

/** A field placed in the main column: labeled block, markdown for richtext fields. */
function MainField({ field, value, locale }: { field: FieldDefinition; value: unknown; locale: string }) {
  if (field.field_type === 'relation') {
    return <RelationFieldRow label={fieldLabel(field, locale)} value={value} targetType={field.settings?.target_type as string | undefined} />
  }
  const rendered = renderFieldValue(value, locale, field.field_type)
  if (!rendered) return null
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)', marginBottom: 6 }}>
        {fieldLabel(field, locale)}
      </div>
      {field.field_type === 'richtext' ? richText(rendered) : (
        <div style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>{rendered}</div>
      )}
    </div>
  )
}

/** A field placed in the sidebar: compact key/value row. */
function SidebarField({ field, value, locale }: { field: FieldDefinition; value: unknown; locale: string }) {
  if (field.field_type === 'relation') {
    return <RelationFieldRow label={fieldLabel(field, locale)} value={value} targetType={field.settings?.target_type as string | undefined} />
  }
  const rendered = renderFieldValue(value, locale, field.field_type)
  const href = field.field_type === 'authority' ? authorityUrl(value) : field.field_type === 'pid' ? pidUrl(value) : undefined
  return rendered ? <MetaRow label={fieldLabel(field, locale)} value={rendered} href={href} /> : null
}

interface DetailPageLayoutProps {
  /** Media/viewer area (IIIF viewer, map, image grid, or null) — rendered above the description. */
  media?: ReactNode
  fieldDefs: FieldDefinition[]
  metadata: Record<string, unknown>
  locale: string
  sidebarPosition: 'left' | 'right'
  /** Extra content rendered in the main column, after generic main fields and before relations (e.g. keyword tags, linked-objects grid). */
  mainExtra?: ReactNode
  /** Extra content rendered in the sidebar, before generic sidebar fields (e.g. inventory number). */
  sidebarBefore?: ReactNode
  /** Extra content rendered in the sidebar, after generic sidebar fields (e.g. type label, coordinates). */
  sidebarExtra?: ReactNode
  relations?: ReactNode
}

/**
 * Renders a portal record's detail page body (media + description + fields + relations,
 * with a metadata sidebar) from field_definitions' detail_slot/detail_role, so schema
 * admins control layout instead of it being hardcoded per record type.
 */
export function DetailPageLayout({
  media, fieldDefs, metadata, locale, sidebarPosition, mainExtra, sidebarBefore, sidebarExtra, relations,
}: DetailPageLayoutProps) {
  const detailFields = fieldDefs.filter(f => f.show_in_detail)
  const descriptionField = detailFields.find(f => f.detail_role === 'description')
  const description = descriptionField ? renderFieldValue(metadata[descriptionField.name], locale, descriptionField.field_type) : null
  const otherFields = detailFields.filter(f => f !== descriptionField)
  const mainFields = otherFields.filter(f => f.detail_slot === 'main')
  const sidebarFields = otherFields.filter(f => f.detail_slot !== 'main')

  return (
    <div className={`detail-layout${sidebarPosition === 'left' ? ' detail-layout--sidebar-left' : ''}`}>
      <div className="detail-main">
        {media}
        {description && (descriptionField!.field_type === 'richtext' ? richText(description) : (
          <div style={{ marginTop: media ? 20 : 0, fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>{description}</div>
        ))}
        {mainFields.map(f => <MainField key={f.name} field={f} value={metadata[f.name]} locale={locale} />)}
        {mainExtra}
        {relations}
      </div>
      <aside className="detail-meta">
        {sidebarBefore}
        {sidebarFields.map(f => <SidebarField key={f.name} field={f} value={metadata[f.name]} locale={locale} />)}
        {sidebarExtra}
      </aside>
    </div>
  )
}
