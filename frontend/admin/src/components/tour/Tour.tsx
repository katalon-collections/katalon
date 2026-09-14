// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTranslation } from 'react-i18next'
import Joyride, { ACTIONS, EVENTS, STATUS, type CallBackProps, type Step, type TooltipRenderProps } from 'react-joyride'
import { basicTourSteps, advancedTourSteps, type TourStep } from '../../tour/steps'
import { users } from '../../api/client'

export type TourVariant = 'basic' | 'advanced'

interface Props {
  variant: TourVariant | null
  route: string
  navigate: (route: string, id?: string | null) => void
  onDone: () => void
}

function toJoyrideSteps(steps: TourStep[]): Step[] {
  return steps.map(s => ({
    target: s.target,
    title: s.title,
    content: s.content,
    placement: s.placement ?? (s.target === 'body' ? 'center' : 'auto'),
    disableBeacon: true,
    spotlightClicks: true,
  }))
}

export function Tour({ variant, route, navigate, onDone }: Props) {
  const { t } = useTranslation('tour')
  const tourSteps = variant === 'advanced' ? advancedTourSteps : basicTourSteps
  const [stepIndex, setStepIndex] = useState(0)
  const [run, setRun] = useState(false)
  const pendingIndexRef = useRef<number | null>(null)

  useEffect(() => {
    if (!variant) return
    setStepIndex(0)
    setRun(true)
  }, [variant])

  useEffect(() => {
    document.body.style.overflow = run ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [run])

  useEffect(() => {
    if (pendingIndexRef.current === null) return
    const nextIndex = pendingIndexRef.current
    pendingIndexRef.current = null
    const raf = requestAnimationFrame(() => {
      setStepIndex(nextIndex)
      setRun(true)
    })
    return () => cancelAnimationFrame(raf)
  }, [route])

  function renderTooltip(props: TooltipRenderProps) {
    const { backProps, closeProps, index, isLastStep, primaryProps, skipProps, step, tooltipProps } = props
    return (
      <div className="react-joyride__tooltip" style={step.styles.tooltip} {...tooltipProps}>
        <div style={step.styles.tooltipContainer}>
          {step.title && <h1 style={step.styles.tooltipTitle}>{step.title}</h1>}
          <div style={step.styles.tooltipContent}>{step.content}</div>
        </div>
        <div style={{ ...step.styles.tooltipFooter, gap: 8 }}>
          <div style={step.styles.tooltipFooterSpacer}>
            {step.showSkipButton && !isLastStep && <button type="button" style={step.styles.buttonSkip} {...skipProps} />}
          </div>
          <button
            type="button"
            style={{
              ...step.styles.buttonNext,
              backgroundColor: 'transparent',
              border: '1px solid var(--accent, #2563eb)',
              color: 'var(--accent, #2563eb)',
              margin: 0,
            }}
            onClick={() => setRun(false)}
          >
            {t('tryItOut')}
          </button>
          {index > 0 && <button type="button" style={{ ...step.styles.buttonBack, margin: 0 }} {...backProps} />}
          <button type="button" style={{ ...step.styles.buttonNext, margin: 0, whiteSpace: 'nowrap' }} {...primaryProps} />
        </div>
        {!step.hideCloseButton && <button style={step.styles.buttonClose} {...closeProps}>×</button>}
      </div>
    )
  }

  if (!variant) return null

  function finish() {
    setRun(false)
    users.setOwnOnboarding(true).catch(() => {})
    onDone()
  }

  function goToIndex(nextIndex: number) {
    const nextStep = tourSteps[nextIndex]
    if (!nextStep) { finish(); return }
    if (nextStep.route !== route) {
      setRun(false)
      pendingIndexRef.current = nextIndex
      navigate(nextStep.route)
    } else {
      setStepIndex(nextIndex)
    }
  }

  function handleCallback(data: CallBackProps) {
    const { status, type, action, index } = data

    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      finish()
      return
    }

    if (type === EVENTS.TARGET_NOT_FOUND) {
      goToIndex(action === ACTIONS.PREV ? index - 1 : index + 1)
      return
    }

    if (type === EVENTS.STEP_AFTER) {
      goToIndex(action === ACTIONS.PREV ? index - 1 : index + 1)
    }
  }

  return createPortal(
    <>
      <Joyride
        steps={toJoyrideSteps(tourSteps)}
        stepIndex={stepIndex}
        run={run}
        continuous
        showSkipButton
        showProgress
        disableScrolling
        callback={handleCallback}
        tooltipComponent={renderTooltip}
        locale={{
          back: t('locale.back'),
          close: t('locale.close'),
          last: t('locale.last'),
          next: t('locale.next'),
          nextLabelWithProgress: t('locale.nextLabelWithProgress'),
          skip: t('locale.skip'),
        }}
        styles={{ options: { primaryColor: 'var(--accent, #2563eb)', width: 440, zIndex: 10000 } }}
      />
      {!run && (
        <div
          className="bb"
          style={{ position: 'fixed', bottom: '1rem', right: '1rem', left: 'auto', zIndex: 10001, margin: 0 }}
        >
          <span>
            {t('paused', { current: stepIndex + 1, total: tourSteps.length })}
          </span>
          <button type="button" onClick={() => setRun(true)}>
            {t('resume')}
          </button>
          <button type="button" onClick={finish}>
            {t('cancel')}
          </button>
        </div>
      )}
    </>,
    document.body,
  )
}
