import { Clock } from 'lucide-react'
import { nowTime } from '../utils.js'
import { Card, FieldError } from './ui.jsx'

export default function GeneralInfo({ form, setField, branches, errors, done }) {
  return (
    <Card
      id="infos"
      step={1}
      done={done}
      title="Informations générales"
      subtitle="Qui contrôle, quelle agence, et quand."
    >
      <div className="fields">
        <div className="field">
          <label htmlFor="controller">
            Nom du contrôleur<span className="required">*</span>
          </label>
          <input
            id="controller"
            className={`input${errors.controller ? ' invalid' : ''}`}
            value={form.controller}
            onChange={(e) => setField('controller', e.target.value)}
            placeholder="Prénom Nom"
            autoComplete="name"
          />
          <FieldError>{errors.controller}</FieldError>
        </div>

        <div className="field">
          <label htmlFor="branch">
            Agence<span className="required">*</span>
          </label>
          <select
            id="branch"
            className={`select${errors.branch ? ' invalid' : ''}`}
            value={form.branch}
            onChange={(e) => setField('branch', e.target.value)}
          >
            <option value="">Choisissez une agence…</option>
            {branches.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
          <FieldError>{errors.branch}</FieldError>
        </div>

        <div className="field">
          <label htmlFor="date">
            Date du contrôle<span className="required">*</span>
          </label>
          <input
            id="date"
            type="date"
            className={`input${errors.date ? ' invalid' : ''}`}
            value={form.date}
            onChange={(e) => setField('date', e.target.value)}
          />
          <FieldError>{errors.date}</FieldError>
        </div>

        <div className="field">
          <label htmlFor="time">
            Heure<span className="required">*</span>
          </label>
          <div className="input-row">
            <input
              id="time"
              type="time"
              step="60"
              className={`input${errors.time ? ' invalid' : ''}`}
              value={form.time}
              onChange={(e) => setField('time', e.target.value)}
            />
            <button
              type="button"
              className="btn btn-ghost sm"
              onClick={() => setField('time', nowTime())}
              title="Mettre l'heure actuelle"
              style={{ minHeight: 46 }}
            >
              <Clock size={16} aria-hidden="true" />
              <span className="sr-only">Mettre l'heure actuelle</span>
            </button>
          </div>
          <FieldError>{errors.time}</FieldError>
        </div>
      </div>
    </Card>
  )
}
