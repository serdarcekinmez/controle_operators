import { useRef, useState } from 'react'
import { CircleAlert, CircleCheck, FileText, Image, Trash2, Upload } from 'lucide-react'
import { formatSize } from '../utils.js'
import { Card, Spinner } from './ui.jsx'

function statusLine(doc) {
  if (doc.status === 'checking') {
    return (
      <span className="file-status">
        <Spinner size={14} /> Vérification…
      </span>
    )
  }
  if (doc.status === 'error') {
    return (
      <span className="file-status error">
        <CircleAlert size={14} aria-hidden="true" /> {doc.message}
      </span>
    )
  }
  return (
    <span className="file-status ok">
      <CircleCheck size={14} aria-hidden="true" />
      {doc.kind === 'image'
        ? 'Prêt — image convertie en page PDF'
        : `Prêt — PDF de ${doc.pages} page${doc.pages > 1 ? 's' : ''}`}
      <span style={{ color: 'var(--text-faint)' }}>· {formatSize(doc.file.size)}</span>
    </span>
  )
}

export default function Documents({ docs, onAdd, onRemove, extensions }) {
  const inputRef = useRef(null)
  const [over, setOver] = useState(false)
  const accept = extensions.map((e) => `.${e}`).join(',')

  const handleFiles = (fileList) => {
    const files = Array.from(fileList || [])
    if (files.length) onAdd(files)
  }

  return (
    <Card
      id="documents"
      step={4}
      title="Documents scannés"
      subtitle="Facultatif — ils sont ajoutés à la suite du rapport PDF."
    >
      <div
        className={`dropzone${over ? ' over' : ''}`}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          handleFiles(e.dataTransfer.files)
        }}
      >
        <Upload size={26} aria-hidden="true" />
        <strong>Glissez vos documents ici, ou cliquez pour les choisir</strong>
        <span>PDF, JPG, JPEG ou PNG — les images sont converties en pages PDF.</span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          hidden
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {docs.length > 0 && (
        <ul className="file-list">
          {docs.map((doc) => {
            const Icon = doc.kind === 'image' ? Image : FileText
            return (
              <li key={doc.id} className={`file-item${doc.status === 'error' ? ' error' : ''}`}>
                <Icon size={22} className="file-icon" aria-hidden="true" />
                <div className="file-meta">
                  <span className="file-name" title={doc.file.name}>
                    {doc.file.name}
                  </span>
                  {statusLine(doc)}
                </div>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => onRemove(doc.id)}
                  aria-label={`Retirer ${doc.file.name}`}
                  title="Retirer ce document"
                >
                  <Trash2 size={18} />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
