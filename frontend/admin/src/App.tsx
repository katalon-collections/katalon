import { AppShell } from './components/layout/AppShell'

// Stub-Screens damit AppShell importieren kann bevor alle Screens fertig sind
import { ScreenList } from './components/screens/ScreenList'
import { ScreenSchema } from './components/screens/ScreenSchema'
import { ScreenVocab } from './components/screens/ScreenVocab'
import { ScreenImporter } from './components/screens/ScreenImporter'
import { ScreenAudit } from './components/screens/ScreenAudit'

export function App() {
  return <AppShell />
}
