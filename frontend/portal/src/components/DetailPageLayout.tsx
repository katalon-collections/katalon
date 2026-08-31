import type { ReactNode } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { FieldDefinition } from '../hooks/useFieldDefinitions'
import { authorityUrl, pidUrl, renderFieldValue, urlHref } from '../utils/renderFieldValue'
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

function GeoNamesMaps({ value }: { value: unknown }) {
  const entries = Array.isArray(value) ? value : [value]
  const maps = entries.flatMap(entry => {
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) return []
    const authority = entry as Record<string, unknown>
    const coordinates = authority.coordinates
    if (authority.source !== 'geonames' || typeof coordinates !== 'object' || coordinates === null) return []
    const { lat, lng } = coordinates as Record<string, unknown>
    if (typeof lat !== 'number' || typeof lng !== 'number' || !Number.isFinite(lat) || !Number.isFinite(lng)
      || Math.abs(lat) > 90 || Math.abs(lng) > 180) return []
    return [{ label: typeof authority.label === 'string' ? authority.label : authority.external_id, lat, lng }]
  })

  return maps.map(({ label, lat, lng }, index) => {
    const bbox = `${lng - 0.05},${lat - 0.03},${lng + 0.05},${lat + 0.03}`
    const src = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`
    return (
      <details key={`${label}-${index}`} style={{ margin: '-6px 0 14px' }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, color: 'var(--fg-2)' }}>OpenStreetMap</summary>
        <iframe
          src={src}
          title={`OpenStreetMap: ${label}`}
          width="100%"
          height="240"
          style={{ border: '1px solid var(--border)', borderRadius: 6, display: 'block', marginTop: 6 }}
          loading="lazy"
        />
      </details>
    )
  })
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
  const href = field.field_type === 'url'
    ? urlHref(value)
    : field.field_type === 'pid'
      ? pidUrl(value)
      : field.field_type === 'authority'
        ? authorityUrl(value)
        : undefined
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: 'var(--fg-3)', marginBottom: 6 }}>
        {fieldLabel(field, locale)}
      </div>
      {field.field_type === 'richtext' ? richText(rendered) : (
        <div style={{ fontSize: 14, lineHeight: 1.65, color: 'var(--fg-2)' }}>
          {href ? <a href={href} target="_blank" rel="noreferrer">{rendered}</a> : rendered}
        </div>
      )}
      {field.field_type === 'authority' && <GeoNamesMaps value={value} />}
    </div>
  )
}

/** A field placed in the sidebar: compact key/value row. */
function SidebarField({ field, value, locale }: { field: FieldDefinition; value: unknown; locale: string }) {
  if (field.field_type === 'relation') {
    return <RelationFieldRow label={fieldLabel(field, locale)} value={value} targetType={field.settings?.target_type as string | undefined} />
  }
  const rendered = renderFieldValue(value, locale, field.field_type)
  const href = field.field_type === 'url'
    ? urlHref(value)
    : field.field_type === 'authority'
      ? authorityUrl(value)
      : field.field_type === 'pid'
        ? pidUrl(value)
        : undefined
  return rendered ? <>
    <MetaRow label={fieldLabel(field, locale)} value={rendered} href={href} />
    {field.field_type === 'authority' && <GeoNamesMaps value={value} />}
  </> : null
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

  const sidebar = (
    <aside className="detail-meta">
      {sidebarBefore}
      {sidebarFields.map(f => <SidebarField key={f.name} field={f} value={metadata[f.name]} locale={locale} />)}
      {sidebarExtra}
    </aside>
  )

  // Media, description, extra content and relations are all optional per record type/record —
  // a metadata-only record (no media, nothing in the main slot, no relations) shouldn't leave
  // a wide empty column next to a narrow sidebar. Callers pass falsy (not an always-truthy
  // wrapper element) for mainExtra/relations when there's nothing to render, so this is reliable.
  const hasMainContent = Boolean(media) || Boolean(description) || mainFields.length > 0 || Boolean(mainExtra) || Boolean(relations)
  if (!hasMainContent) {
    return <div className="detail-layout detail-layout--metadata-only">{sidebar}</div>
  }

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
      {sidebar}
    </div>
  )
}
