# Design QA: Issue #277

## Evidence

- Source visual truth, picker: `/Users/karl/.codex/generated_images/019fecf9-bc7b-7540-8277-6c69ea22e53a/exec-779b87db-1dc2-491d-be70-1bc0d7978885.png`
- Source visual truth, quick-create modal: `/Users/karl/.codex/generated_images/019fecf9-bc7b-7540-8277-6c69ea22e53a/exec-85b6bcdc-3fda-4e1d-a305-8fc7e481e0df.png`
- Source dimensions: both 1487 x 1058 px; no density metadata was available.
- Rendered implementation: Katalon Admin at `http://127.0.0.1:5173/`, authenticated as administrator, existing Object record open.
- Desktop viewport: 1280 x 800 CSS px. Paseo captured the implementation at 2560 x 1600 px (device scale factor 2).
- Implementation screenshot path: unavailable. The browser-rendered states were inspected, but the captures were not persisted successfully.
- Mobile viewport: not captured.

## States inspected

- General relationships panel on an existing Object record.
- Picker with all five target types visible: Object, Entity, Place, Occurrence, Procedure.
- Relation type selected and `Neues Objekt anlegen` enabled.
- Native quick-create dialog open with draft notice, schema-driven Object fields, `Abbrechen`, close control, and `Entwurf anlegen und verknüpfen`.
- Parent form remained visible behind the dialog.

## Findings

- [P0] No browser-rendered implementation screenshot is available for the required combined comparison input.
  - Location: desktop picker and quick-create dialog.
  - Evidence: both source images opened and the corresponding rendered states were reached, but the implementation captures were not persisted and therefore could not be combined with the sources.
  - Impact: visual fidelity cannot be signed off from durable side-by-side evidence.
  - Fix: recapture picker and modal at the matching desktop viewport, persist the PNGs, and compare each source/implementation pair in one comparison input.
- [P1] The 375 px responsive state was not captured or compared.
  - Location: quick-create dialog and picker at mobile width.
  - Evidence: the desktop state was reached; the browser run ended before resize, scroll, overflow, focus-return, Escape, and 44 px touch-target checks.
  - Impact: the approved full-screen mobile behavior and accessibility acceptance remain visually unverified.
  - Fix: repeat the browser pass at 375 px width and record viewport, screenshot dimensions, horizontal overflow, dialog scrolling, touch-target measurements, Escape behavior, and focus return.

## Required fidelity surfaces

- Fonts and typography: visible desktop hierarchy appeared consistent with the existing Katalon design system; exact comparison blocked by missing combined evidence.
- Spacing and layout rhythm: picker grouping and centered modal were visible; exact spacing, crop, rhythm, and mobile layout remain blocked.
- Colors and visual tokens: implementation used existing Katalon tokens and draft styling; token fidelity to the source was not jointly compared.
- Image quality and asset fidelity: the target contains no product imagery; icon and raster fidelity were not compared at normalized density.
- Copy and content: visible labels matched the approved flow, including the numbered picker steps, draft notice, and create-and-link action.

## Interaction and technical evidence

- Login, record navigation, target-type selection, relation-type selection, create-action enablement, and modal opening were exercised in the in-app browser.
- No target record was created during this visual pass.
- Console/network review was opened earlier in the session; no console messages were reported at that point. A final modal-state console check was not completed.
- The green automated E2E UX check is separate behavioral evidence. It does not replace the missing browser-rendered visual comparison and is not treated as a visual pass.

## Focused region comparison

Not completed. The picker controls and modal header/actions require focused comparisons, but no persisted implementation screenshots were available to place beside the source images.

## Comparison history

- Pass 1: source images available; desktop picker and modal states reached. No P0/P1/P2 visual mismatch was adjudicated because the required same-input comparison could not be completed. No visual fixes were made.

## Implementation checklist

1. Persist desktop picker and modal screenshots at the matched state and viewport.
2. Put each source and implementation capture into one normalized comparison input.
3. Capture and compare the 375 px state, including scroll, overflow, touch targets, Escape, and focus return.
4. Re-run the five fidelity-surface review and console check.

final result: blocked
