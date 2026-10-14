// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Karl Krägelin

import { useEffect } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'

/** Scrolls to the top when a link or navigate() opens another page. Query-only
 *  changes (search filters) keep the position; back/forward (POP) is left to the
 *  browser's own scroll restoration. */
export function ScrollToTop() {
  const { pathname } = useLocation()
  const navigationType = useNavigationType()

  useEffect(() => {
    if (navigationType !== 'POP') window.scrollTo(0, 0)
    // Only a path change counts as a new page; navigationType is read for it.
  }, [pathname])

  return null
}
