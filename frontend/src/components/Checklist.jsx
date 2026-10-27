import { Check, MessageSquareText, TriangleAlert } from 'lucide-react'
import { Card, Chip, FieldError } from './ui.jsx'

const STATE_TEXT = { ok: 'Conforme', problem: 'Anomalie constatée' }

export default function Checklist({ items, statuses, comments, onStatus, onComment, errors }) {
  const answered = items.filter((i) => statuses[i.key]).length
  const problems = items.filter((i) => statuses[i.key] === 'problem').length
  const complete = answered === items.length

  return (
    <Card
      id="points"
      step={2}
      done={complete && problems === 0}
      title="Points de contrôle niveau 1"
      subtitle="Cliquez sur OK ou Anomalie pour chaque point. Un nouveau clic annule le choix."
      extra={
        problems > 0 ? (
          <Chip kind="error" icon={TriangleAlert}>
            {problems} anomalie{problems > 1 ? 's' : ''}
          </Chip>
        ) : complete ? (
          <Chip kind="success" icon={Check}>
            Tout est conforme
          </Chip>
        ) : null
      }
    >
      <div className="progress">
        <div
          className={`progress-bar${complete ? ' complete' : ''}`}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={items.length}
          aria-valuenow={answered}
          aria-label="Points renseignés"
        >
          <span style={{ width: `${(answered / items.length) * 100}%` }} />
        </div>
        <span className="progress-label">
          {answered}/{items.length} renseigné{answered > 1 ? 's' : ''}
        </span>
      </div>

      <div className="checklist">
        {items.map((item) => {
          const status = statuses[item.key] || ''
          const commentError = errors[`comment_${item.key}`]
          return (
            <div
              key={item.key}
              className={`check-item${status === 'ok' ? ' is-ok' : ''}${status === 'problem' ? ' is-problem' : ''}`}
            >
              <div className="check-row">
                <div className="check-label">
                  {item.label}
                  <span className="check-state">{STATE_TEXT[status] || 'Non renseigné'}</span>
                </div>
                <div className="seg" role="group" aria-label={item.label}>
                  <button
                    type="button"
                    className="seg-btn ok"
                    aria-pressed={status === 'ok'}
                    onClick={() => onStatus(item.key, 'ok')}
                  >
                    <Check size={18} aria-hidden="true" /> OK
                  </button>
                  <button
                    type="button"
                    className="seg-btn pb"
                    aria-pressed={status === 'problem'}
                    onClick={() => onStatus(item.key, 'problem')}
                  >
                    <TriangleAlert size={17} aria-hidden="true" /> Anomalie
                  </button>
                </div>
              </div>

              {status === 'problem' && (
                <div className="comment-box">
                  <label htmlFor={`comment_${item.key}`}>
                    <MessageSquareText size={16} aria-hidden="true" />
                    Détail de l'anomalie (obligatoire)
                  </label>
                  <textarea
                    id={`comment_${item.key}`}
                    className={`textarea${commentError ? ' invalid' : ''}`}
                    value={comments[item.key] || ''}
                    onChange={(e) => onComment(item.key, e.target.value)}
                    placeholder="Décrivez l'anomalie constatée…"
                    autoFocus={!comments[item.key]}
                  />
                  <FieldError>{commentError}</FieldError>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
