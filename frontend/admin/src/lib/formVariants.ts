import type { FormVariant } from '../types'

export function localVariantKey(recordType: string, subtype?: string | null): string {
  return `katalon_form_variant_${recordType}_${subtype ?? ''}`
}

// Sentinel stored when the user explicitly picks "Vollständig" (full schema,
// no variant) — distinct from "nothing remembered yet", so an explicit choice
// isn't overridden by role/global defaults on the next visit.
export const FULL_SCHEMA_CHOICE = '__full__'

/**
 * Priority chain: context override > remembered manual choice > role default >
 * global default > null (fallback = full schema, current behavior).
 */
export function resolveActiveVariant(
  variants: FormVariant[],
  currentRole: string,
  rememberedId: string | null,
  contextHint?: string | null,
): FormVariant | null {
  if (contextHint) {
    const hinted = variants.find(v => v.id === contextHint)
    if (hinted) return hinted
  }
  if (rememberedId === FULL_SCHEMA_CHOICE) return null
  if (rememberedId) {
    const remembered = variants.find(v => v.id === rememberedId)
    if (remembered) return remembered
  }
  const roleDefault = variants.find(v => v.default_for_roles.includes(currentRole))
  if (roleDefault) return roleDefault
  const globalDefault = variants.find(v => v.is_default_global)
  if (globalDefault) return globalDefault
  return null
}
