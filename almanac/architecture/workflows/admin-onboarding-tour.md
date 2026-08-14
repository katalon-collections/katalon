---
title: "Admin Onboarding Tour"
summary: "A guided, non-blocking react-joyride tour walks new admins and superusers through the first Admin setup steps and can be restarted from the profile settings."
topics: [architecture, workflows, frontend, onboarding]
sources:
  - id: admin-package
    type: file
    path: frontend/admin/package.json
  - id: tour-component
    type: file
    path: frontend/admin/src/components/tour/Tour.tsx
  - id: tour-steps
    type: file
    path: frontend/admin/src/tour/steps.ts
  - id: app-shell
    type: file
    path: frontend/admin/src/components/layout/AppShell.tsx
  - id: sidebar
    type: file
    path: frontend/admin/src/components/layout/Sidebar.tsx
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: schema-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSchema.tsx
  - id: list-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenList.tsx
  - id: form-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenForm.tsx
  - id: users-api
    type: file
    path: backend/src/katalon/api/v1/users.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: onboarding-migration
    type: file
    path: backend/migrations/versions/0030_add_user_onboarding_completed_at.py
---

`User.onboarding_completed_at` is a nullable timestamp added by migration `0030`; it tracks whether a user has finished the tour [@models] [@onboarding-migration]. `AppShell` fetches `users.me()` after login and auto-starts the basic tour when the current user's role is `admin` or `superuser` and the timestamp is unset [@app-shell]. An admin or superuser can restart the basic or advanced tour from the profile section of Settings [@settings-screen] [@app-shell].

`Tour` wraps `react-joyride`; the Admin package currently depends on `react-joyride` `^2.9.3`, and the component uses that package's `callback`, `CallBackProps`, `Step`, and `TooltipRenderProps` API [@admin-package] [@tour-component]. Steps carry a `route` field; `Tour` only calls `AppShell`'s `navigate` when a step's route differs from the current route, then waits one animation frame before advancing `stepIndex` so the target element has mounted [@tour-component]. `EVENTS.TARGET_NOT_FOUND` auto-advances past a step instead of stalling. Steps anchored to state-dependent UI, such as an open field editor or a saved record's media, relations, or status sections, are skipped when that UI is not present yet; this keeps the tour non-blocking through `spotlightClicks` and the Joyride finish/skip callback path [@tour-component] [@tour-steps].

The custom tooltip adds an `Ausprobieren` button that pauses the current tour by setting `run` to `false` without marking onboarding complete; the floating pause bar can resume the same step or abort, and aborting uses the same `finish()` path as Skip and Finish [@tour-component]. Because `tooltipComponent` replaces Joyride's default tooltip chrome, visible controls must be rendered inside `renderTooltip`; a visible `Überspringen` button must not depend on an unset step-local flag or an empty button body [@tour-component]. The first basic-tour step tells users about `Ausprobieren`, `Überspringen`, and the restart path in Settings > Profile, while the Settings profile section exposes buttons for the basic and advanced tours through `onStartTour` [@tour-steps] [@settings-screen].

Two step arrays live in `tour-steps`: `basicTourSteps` covers subtypes, schema, vocabulary, relation types, first object creation, relations, media, publication status, and OAI sets; `advancedTourSteps` covers form variants, import, authority sources, inherited fields, procedures, users, audit log, and static pages [@tour-steps]. Both target elements via `data-tour="..."` attributes. Sidebar navigation buttons derive generic `nav-<route-id>` targets from their route ids, while the in-screen targets are explicit attributes on the field-type select in `ScreenSchema`, the new-record button in `ScreenList`, and the status, media, and relations sections in `ScreenForm` [@sidebar] [@schema-screen] [@list-screen] [@form-screen].

`PUT /v1/users/me/onboarding` sets or clears the timestamp [@users-api]. Finishing, skipping, or aborting a tour calls it with `completed: true`; the current `Tour` component never calls the endpoint with `completed: false` [@tour-component].
