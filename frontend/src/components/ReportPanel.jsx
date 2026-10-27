import {
  CircleCheck,
  CircleDashed,
  CircleX,
  Download,
  ExternalLink,
  FileText,
  Mail,
  RotateCcw,
  TriangleAlert,
} from 'lucide-react'
import { Alert, Card, Spinner } from './ui.jsx'

const ICONS = { ok: CircleCheck, warn: TriangleAlert, bad: CircleX, todo: CircleDashed }

function StatusList({ items }) {
  return (
    <ul className="status-list">
      {items.map((item) => {
        const Icon = ICONS[item.level]
        return (
          <li key={item.label}>
            <Icon size={19} className={`s-icon s-${item.level}`} aria-hidden="true" />
            <span className="s-label">{item.label}</span>
            <span className={`s-${item.level}`} style={{ fontWeight: 650, fontSize: '0.88rem' }}>
              {item.value}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

export default function ReportPanel({ status, busy, message, onClearMessage, report, onCreate, onNew }) {
  return (
    <Card id="rapport" title="Finaliser le contrôle" subtitle="Où en êtes-vous ?">
      <StatusList items={status} />

      <div className="section-gap">
        {message && (
          <Alert kind={message.kind} onClose={onClearMessage}>
            {message.text}
          </Alert>
        )}

        <button type="button" className="btn btn-primary block lg" onClick={onCreate} disabled={busy}>
          {busy ? <Spinner size={19} /> : <FileText size={19} aria-hidden="true" />}
          {busy ? 'Création du rapport…' : report ? 'Recréer le rapport PDF' : 'Créer le rapport PDF'}
        </button>
        <p className="hint">
          Le rapport réunit la fiche de contrôle et vos documents scannés en un seul PDF. Il est
          aussi enregistré automatiquement dans votre fichier Excel.
        </p>

        {report && (
          <>
            <Alert kind={report.stale ? 'warning' : 'success'} title={report.stale ? 'Rapport à recréer' : 'Rapport PDF créé'}>
              {report.stale
                ? 'Le formulaire a changé depuis la création du rapport : cliquez sur « Recréer le rapport PDF ».'
                : `${report.filename} — une copie est conservée sur ce poste (dossier « reports »).`}
              {report.warnings?.length > 0 && (
                <ul>
                  {report.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              )}
            </Alert>
            <div className="btn-row">
              <a className="btn btn-success" href={report.url} target="_blank" rel="noreferrer">
                <ExternalLink size={18} aria-hidden="true" />
                Ouvrir le PDF
              </a>
              <a className="btn btn-secondary" href={`${report.url}?download=1`}>
                <Download size={18} aria-hidden="true" />
                Télécharger
              </a>
            </div>
          </>
        )}

        <button
          type="button"
          className="btn btn-ghost block"
          disabled
          title="Bientôt disponible : envoi par Outlook (Microsoft 365)."
        >
          <Mail size={18} aria-hidden="true" />
          Envoyer par e-mail
          <span className="coming-soon">Bientôt — Outlook</span>
        </button>

        {report && (
          <button type="button" className="btn btn-secondary block" onClick={onNew}>
            <RotateCcw size={18} aria-hidden="true" />
            Commencer un nouveau contrôle
          </button>
        )}
      </div>
    </Card>
  )
}
