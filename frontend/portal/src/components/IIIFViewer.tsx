import Viewer from '@samvera/clover-iiif/viewer'

interface Props {
  manifestUrl: string
  onError?: () => void
}

const options = {
  background: '#0f172a',
  showTitle: false,
  showIIIFBadge: false,
  showDownload: false,
  informationPanel: {
    open: false,
    renderToggle: false,
    renderAbout: false,
    renderSupplementing: false,
    renderAnnotation: false,
    renderContentSearch: false,
  },
  openSeadragon: {
    gestureSettingsMouse: {
      scrollToZoom: true,
    },
  },
}

export function IIIFViewer({ manifestUrl, onError }: Props) {
  return (
    <div style={{ borderRadius: 10, overflow: 'hidden' }}>
      <Viewer
        iiifContent={manifestUrl}
        options={options}
        canvasIdCallback={() => {
          // no-op: keep onError prop compatible but Clover has no error callback
          void onError
        }}
      />
    </div>
  )
}
