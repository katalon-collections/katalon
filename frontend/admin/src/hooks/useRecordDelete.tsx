// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { objects, entities, places, occurrences, procedures, collections, ConflictError } from '../api/client'
import { ConfirmModal } from '../components/ui/ConfirmModal'
import { DeleteWithChildrenModal } from '../components/ui/DeleteWithChildrenModal'
import type { ListableRecordType } from '../types'

const APIS = {
  object: objects, entity: entities, place: places,
  occurrence: occurrences, procedure: procedures, collection: collections,
}

/** Move a record to the trash, including the confirmations for linked records and child records. */
export function useRecordDelete(recordType: ListableRecordType, typeLabel: string, onDeleted: (id: string) => void) {
  const { t } = useTranslation('screenList')
  const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => Promise<void> } | null>(null)
  const [childTarget, setChildTarget] = useState<{ id: string; childCount: number } | null>(null)

  function confirmForced(message: string, run: () => Promise<void>, id: string) {
    setConfirm({
      message: t('deleteConfirmWithConflicts', { message }),
      onConfirm: async () => {
        try {
          await run()
          onDeleted(id)
        } catch (e) {
          alert((e as Error).message)
        } finally {
          setConfirm(null)
        }
      },
    })
  }

  function requestDelete(id: string) {
    setConfirm({
      message: t('deleteConfirm', { type: typeLabel }),
      onConfirm: async () => {
        try {
          await APIS[recordType].delete(id)
          setConfirm(null)
          onDeleted(id)
        } catch (e) {
          if (e instanceof ConflictError && e.child_count > 0) {
            setConfirm(null)
            setChildTarget({ id, childCount: e.child_count })
          } else if (e instanceof ConflictError) {
            confirmForced(e.message, () => APIS[recordType].delete(id, true), id)
          } else {
            alert((e as Error).message)
            setConfirm(null)
          }
        }
      },
    })
  }

  async function deleteWithChildren(id: string, action: 'cascade' | 'reparent') {
    const hierarchyApi = recordType === 'place' ? places : collections
    try {
      await hierarchyApi.deleteHierarchy(id, { [action]: true })
      setChildTarget(null)
      onDeleted(id)
    } catch (e) {
      if (!(e instanceof ConflictError)) throw e
      setChildTarget(null)
      confirmForced(e.message, () => hierarchyApi.deleteHierarchy(id, { [action]: true, force: true }), id)
    }
  }

  const dialogs = (
    <>
      {confirm && (
        <ConfirmModal
          message={confirm.message}
          confirmLabel={t('deleteRowTitle')}
          cancelLabel={t('cancel')}
          danger
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}
      {childTarget && (
        <DeleteWithChildrenModal
          title={t('deleteChildrenModal.title')}
          description={t('deleteConfirm', { type: typeLabel })}
          warningTitle={t('deleteChildrenModal.warningTitle')}
          warningText={t(childTarget.childCount === 1 ? 'deleteChildrenModal.warning' : 'deleteChildrenModal.warning_plural', { count: childTarget.childCount })}
          chooseActionLabel={t('deleteChildrenModal.chooseAction')}
          reparentLabel={t('deleteChildrenModal.optionReparent')}
          reparentDesc={t('deleteChildrenModal.optionReparentDesc')}
          cascadeLabel={t('deleteChildrenModal.optionCascade')}
          cascadeDesc={t('deleteChildrenModal.optionCascadeDesc')}
          cancelLabel={t('cancel')}
          confirmLabel={t('deleteRowTitle')}
          deletingLabel={t('deleting')}
          onConfirm={action => deleteWithChildren(childTarget.id, action)}
          onCancel={() => setChildTarget(null)}
        />
      )}
    </>
  )

  return { requestDelete, dialogs }
}
