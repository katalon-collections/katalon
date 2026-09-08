// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import de from './locales/de.json'
import en from './locales/en.json'
import deAuthorityInput from './locales/de/authorityInput.json'
import enAuthorityInput from './locales/en/authorityInput.json'
import deBatchEditModal from './locales/de/batchEditModal.json'
import enBatchEditModal from './locales/en/batchEditModal.json'
import deFeedbackButton from './locales/de/feedbackButton.json'
import enFeedbackButton from './locales/en/feedbackButton.json'
import deRichTextEditor from './locales/de/richTextEditor.json'
import enRichTextEditor from './locales/en/richTextEditor.json'
import deScreenForm from './locales/de/screenForm.json'
import enScreenForm from './locales/en/screenForm.json'
import deScreenFormVariants from './locales/de/screenFormVariants.json'
import enScreenFormVariants from './locales/en/screenFormVariants.json'
import deScreenFormSections from './locales/de/screenFormSections.json'
import enScreenFormSections from './locales/en/screenFormSections.json'
import deScreenImporter from './locales/de/screenImporter.json'
import enScreenImporter from './locales/en/screenImporter.json'
import deScreenOAISets from './locales/de/screenOAISets.json'
import enScreenOAISets from './locales/en/screenOAISets.json'
import deScreenSettings from './locales/de/screenSettings.json'
import enScreenSettings from './locales/en/screenSettings.json'
import deScreenVocab from './locales/de/screenVocab.json'
import enScreenVocab from './locales/en/screenVocab.json'
import deStepMedia from './locales/de/stepMedia.json'
import enStepMedia from './locales/en/stepMedia.json'
import deStepResult from './locales/de/stepResult.json'
import enStepResult from './locales/en/stepResult.json'
import deStepUpload from './locales/de/stepUpload.json'
import enStepUpload from './locales/en/stepUpload.json'
import deStepXmlRecordSelector from './locales/de/stepXmlRecordSelector.json'
import enStepXmlRecordSelector from './locales/en/stepXmlRecordSelector.json'
import deTour from './locales/de/tour.json'
import enTour from './locales/en/tour.json'
import deTranslatableInput from './locales/de/translatableInput.json'
import enTranslatableInput from './locales/en/translatableInput.json'
import deScreenAudit from './locales/de/screenAudit.json'
import enScreenAudit from './locales/en/screenAudit.json'
import deScreenBanners from './locales/de/screenBanners.json'
import enScreenBanners from './locales/en/screenBanners.json'
import deScreenExport from './locales/de/screenExport.json'
import enScreenExport from './locales/en/screenExport.json'
import deScreenUsers from './locales/de/screenUsers.json'
import enScreenUsers from './locales/en/screenUsers.json'
import deScreenSubtype from './locales/de/screenSubtype.json'
import enScreenSubtype from './locales/en/screenSubtype.json'
import deScreenList from './locales/de/screenList.json'
import enScreenList from './locales/en/screenList.json'
import deScreenPages from './locales/de/screenPages.json'
import enScreenPages from './locales/en/screenPages.json'
import deScreenSchema from './locales/de/screenSchema.json'
import enScreenSchema from './locales/en/screenSchema.json'
import deScreenStorageLocation from './locales/de/screenStorageLocation.json'
import enScreenStorageLocation from './locales/en/screenStorageLocation.json'
import deScreenSparql from './locales/de/screenSparql.json'
import enScreenSparql from './locales/en/screenSparql.json'
import deScreenWorkingSets from './locales/de/screenWorkingSets.json'
import enScreenWorkingSets from './locales/en/screenWorkingSets.json'

const STORAGE_KEY = 'katalon.ui_language'

export const UI_LANGUAGES = ['de', 'en'] as const

function detectLanguage(): string {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored && (UI_LANGUAGES as readonly string[]).includes(stored)) return stored
  return 'de'
}

i18next.use(initReactI18next).init({
  resources: {
    de: {
      translation: de,
      authorityInput: deAuthorityInput,
      batchEditModal: deBatchEditModal,
      feedbackButton: deFeedbackButton,
      richTextEditor: deRichTextEditor,
      screenForm: deScreenForm,
      screenFormVariants: deScreenFormVariants,
      screenFormSections: deScreenFormSections,
      screenImporter: deScreenImporter,
      screenOAISets: deScreenOAISets,
      screenSettings: deScreenSettings,
      screenVocab: deScreenVocab,
      stepMedia: deStepMedia,
      stepResult: deStepResult,
      stepUpload: deStepUpload,
      stepXmlRecordSelector: deStepXmlRecordSelector,
      tour: deTour,
      translatableInput: deTranslatableInput,
      screenAudit: deScreenAudit,
      screenBanners: deScreenBanners,
      screenExport: deScreenExport,
      screenUsers: deScreenUsers,
      screenSubtype: deScreenSubtype,
      screenList: deScreenList,
      screenPages: deScreenPages,
      screenSchema: deScreenSchema,
      screenStorageLocation: deScreenStorageLocation,
      screenSparql: deScreenSparql,
      screenWorkingSets: deScreenWorkingSets,
    },
    en: {
      translation: en,
      authorityInput: enAuthorityInput,
      batchEditModal: enBatchEditModal,
      feedbackButton: enFeedbackButton,
      richTextEditor: enRichTextEditor,
      screenForm: enScreenForm,
      screenFormVariants: enScreenFormVariants,
      screenFormSections: enScreenFormSections,
      screenImporter: enScreenImporter,
      screenOAISets: enScreenOAISets,
      screenSettings: enScreenSettings,
      screenVocab: enScreenVocab,
      stepMedia: enStepMedia,
      stepResult: enStepResult,
      stepUpload: enStepUpload,
      stepXmlRecordSelector: enStepXmlRecordSelector,
      tour: enTour,
      translatableInput: enTranslatableInput,
      screenAudit: enScreenAudit,
      screenBanners: enScreenBanners,
      screenExport: enScreenExport,
      screenUsers: enScreenUsers,
      screenSubtype: enScreenSubtype,
      screenList: enScreenList,
      screenPages: enScreenPages,
      screenSchema: enScreenSchema,
      screenStorageLocation: enScreenStorageLocation,
      screenSparql: enScreenSparql,
      screenWorkingSets: enScreenWorkingSets,
    },
  },
  lng: detectLanguage(),
  fallbackLng: 'de',
  interpolation: { escapeValue: false },
})

export function setUiLanguage(lang: string) {
  localStorage.setItem(STORAGE_KEY, lang)
  i18next.changeLanguage(lang)
}

export default i18next
