import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Power } from 'lucide-react'
import { postJson } from '../api.js'
import { Alert, Spinner } from './ui.jsx'

/**
 * Confirmation avant de quitter : « Avez-vous enregistré votre travail ? ».
 * « Oui, quitter » arrête le serveur local (la fenêtre noire se ferme).
 */
export default function QuitDialog({ open, onCancel, onQuit, unsaved }) {
  const ref = useRef(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  const quit = async () => {
    setBusy(true)
    try {
      await postJson('/api/quit', {})
    } catch {
      /* serveur déjà arrêté : l'application est fermée de toute façon */
    }
    onQuit()
  }

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="quit-title"
      onCancel={(e) => {
        e.preventDefault()
        if (!busy) onCancel()
      }}
    >
      <h2 id="quit-title">Avez-vous enregistré votre travail ?</h2>
      <p className="hint">
        Les contrôles qui n'ont pas été enregistrés dans votre fichier Excel (ou
        téléchargés) seront perdus.
      </p>
      {unsaved && (
        <Alert kind="warning" title="Modifications non enregistrées">
          Votre fichier Excel contient des modifications qui n'ont pas encore été
          écrites ou téléchargées.
        </Alert>
      )}
      <div className="btn-row">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy} autoFocus>
          <ArrowLeft size={18} aria-hidden="true" />
          Retour à l'application
        </button>
        <button type="button" className="btn btn-danger" onClick={quit} disabled={busy}>
          {busy ? <Spinner /> : <Power size={18} aria-hidden="true" />}
          Oui, quitter
        </button>
      </div>
    </dialog>
  )
}
