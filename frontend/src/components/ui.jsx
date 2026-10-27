// Briques d'interface partagées : carte, message, pastille.

import { CircleAlert, CircleCheck, Info, LoaderCircle, TriangleAlert, X } from 'lucide-react'

const ALERT_ICONS = {
  success: CircleCheck,
  error: CircleAlert,
  warning: TriangleAlert,
  info: Info,
}

export function Alert({ kind = 'info', title, children, onClose }) {
  const Icon = ALERT_ICONS[kind]
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      <Icon size={20} aria-hidden="true" />
      <div className="alert-body">
        {title && <strong className="alert-title">{title}</strong>}
        {children}
      </div>
      {onClose && (
        <button type="button" className="alert-close" onClick={onClose} aria-label="Fermer le message">
          <X size={18} />
        </button>
      )}
    </div>
  )
}

export function Card({ step, done, title, subtitle, extra, children, id }) {
  return (
    <section className="card" id={id} aria-labelledby={id ? `${id}-title` : undefined}>
      <div className="card-head">
        {step != null && (
          <span className={`step${done ? ' done' : ''}`} aria-hidden="true">
            {done ? <CircleCheck size={18} /> : step}
          </span>
        )}
        <div>
          <h2 id={id ? `${id}-title` : undefined}>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {extra && <div className="head-extra">{extra}</div>}
      </div>
      {children}
    </section>
  )
}

export function Chip({ kind = 'neutral', icon: Icon, children, onClick, title }) {
  const Tag = onClick ? 'button' : 'span'
  return (
    <Tag
      className={`chip chip-${kind}`}
      onClick={onClick}
      title={title}
      type={onClick ? 'button' : undefined}
    >
      {Icon && <Icon size={15} aria-hidden="true" />}
      {children}
    </Tag>
  )
}

export function Spinner({ size = 18 }) {
  return <LoaderCircle size={size} className="spin" aria-hidden="true" />
}

export function FieldError({ children }) {
  if (!children) return null
  return (
    <span className="field-error">
      <CircleAlert size={15} aria-hidden="true" />
      {children}
    </span>
  )
}
