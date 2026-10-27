import { useMemo, useRef, useState } from 'react'
import {
  ChevronDown,
  Download,
  FilePlus2,
  FileSpreadsheet,
  FolderOpen,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Trash2,
} from 'lucide-react'
import { frDate, normalizeName, plural } from '../utils.js'
import { Alert, Card, Spinner } from './ui.jsx'

function rowLabel(row) {
  return `${frDate(row.date_controle)} à ${row.heure_controle} — ${row.agence} — ${row.controleur}`
}

const rowValue = (r) => `${r.date_controle}|${r.heure_controle}|${r.controleur}`

// Nombre maximal de contrôles affichés par une recherche.
const SEARCH_MAX_RESULTS = 30
const NO_SEARCH = { date: '', controller: '', branch: '' }

/**
 * Contrôles correspondant aux critères (vides = ignorés). Le nom du
 * contrôleur peut être partiel (« dup » trouve « Jean Dupont »).
 */
function searchRows(rows, criteria) {
  const name = normalizeName(criteria.controller)
  return rows.filter(
    (r) =>
      (!criteria.date || r.date_controle === criteria.date) &&
      normalizeName(r.controleur).includes(name) &&
      (!criteria.branch || r.agence === criteria.branch)
  )
}

function FileSummary({ excel }) {
  const pendingWrite = excel.handle && excel.writeFailed
  const memory = !excel.handle
  const cls = pendingWrite || (memory && excel.dirty) ? ' pending' : memory ? ' memory' : ''
  const name = excel.name || 'Nouveau fichier de contrôle'
  const detail = excel.total
    ? `${plural(excel.total, 'contrôle')} · dernier le ${frDate(excel.last)}`
    : 'Aucun contrôle pour le moment'
  const mode = excel.handle
    ? 'Enregistrement direct sur votre ordinateur'
    : 'À télécharger après chaque contrôle'
  return (
    <div className={`file-card${cls}`}>
      <FileSpreadsheet size={30} aria-hidden="true" />
      <div>
        <strong title={name}>{name}</strong>
        <span>{detail}</span>
        <span>{mode}</span>
      </div>
    </div>
  )
}

export default function ExcelPanel({ excel, controller, branches, onSave, saved }) {
  const inputRef = useRef(null)
  const [toDelete, setToDelete] = useState('')
  const [search, setSearch] = useState(NO_SEARCH)
  const [criteria, setCriteria] = useState(null) // critères de la dernière recherche
  const rows = useMemo(() => [...excel.rows].reverse(), [excel.rows])
  const agencies = useMemo(
    () => [...new Set([...branches, ...excel.rows.map((r) => r.agence)])].filter(Boolean).sort(),
    [branches, excel.rows]
  )
  const results = useMemo(() => (criteria ? searchRows(rows, criteria) : []), [rows, criteria])

  const open = () => (excel.canWriteFiles ? excel.openFile() : inputRef.current?.click())

  const deleteRow = async (row) => {
    if (!window.confirm(`Supprimer ce contrôle du fichier ?\n\n${rowLabel(row)}`)) return
    const ok = await excel.remove({
      date: row.date_controle,
      time: row.heure_controle,
      controller: row.controleur,
    })
    if (ok && rowValue(row) === toDelete) setToDelete('')
  }

  const handleDelete = () => {
    const row = rows.find((r) => rowValue(r) === toDelete)
    if (row) deleteRow(row)
  }

  return (
    <Card id="excel" title="Mon fichier Excel" subtitle="Le suivi de tous vos contrôles.">
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) excel.openFromInput(file)
          e.target.value = ''
        }}
      />

      <div className="section-gap">
        {!excel.hasFile ? (
          <>
            <Alert kind="warning" title="Aucun fichier Excel ouvert">
              Ouvrez votre fichier de contrôle pour y enregistrer vos contrôles.
              {excel.sessionRows.length > 0 &&
                ` Les contrôles de cette séance (${excel.sessionRows.length}) y seront ajoutés.`}
            </Alert>
            <div className="btn-col">
              {excel.recalled && (
                <button type="button" className="btn btn-primary block" onClick={excel.resume} disabled={excel.busy}>
                  <RotateCcw size={18} aria-hidden="true" />
                  Reprendre « {excel.recalled.name} »
                </button>
              )}
              <button
                type="button"
                className={`btn ${excel.recalled ? 'btn-secondary' : 'btn-primary'} block`}
                onClick={open}
                disabled={excel.busy}
              >
                <FolderOpen size={18} aria-hidden="true" />
                Ouvrir mon fichier Excel
              </button>
              <button
                type="button"
                className="btn btn-warning block"
                onClick={() => excel.createNew(controller)}
                disabled={excel.busy}
              >
                <FilePlus2 size={18} aria-hidden="true" />
                Première fois ? Créer mon fichier
              </button>
            </div>
          </>
        ) : (
          <>
            <FileSummary excel={excel} />
          </>
        )}

        {excel.busy && (
          <p className="hint" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <Spinner size={16} /> Mise à jour du fichier…
          </p>
        )}

        {excel.message && (
          <Alert kind={excel.message.kind} onClose={() => excel.setMessage(null)}>
            {excel.message.text}
          </Alert>
        )}

        {excel.handle && excel.writeFailed && (
          <button type="button" className="btn btn-warning block" onClick={excel.retryWrite} disabled={excel.busy}>
            <RefreshCw size={18} aria-hidden="true" />
            Réessayer d'écrire dans le fichier
          </button>
        )}

        <button
          type="button"
          className={`btn ${saved || !excel.hasFile ? 'btn-secondary' : 'btn-primary'} block lg`}
          onClick={onSave}
          disabled={excel.busy}
        >
          <Save size={19} aria-hidden="true" />
          {saved ? 'Mettre à jour dans Excel' : 'Enregistrer ce contrôle dans Excel'}
        </button>

        {excel.workbook && (
          <button
            type="button"
            className={`btn ${!excel.handle && excel.dirty ? 'btn-warning' : 'btn-secondary'} block`}
            onClick={() => excel.download(controller)}
          >
            <Download size={18} aria-hidden="true" />
            {excel.handle ? 'Télécharger une copie du fichier' : 'Télécharger le fichier de contrôle'}
          </button>
        )}

        {!excel.handle && excel.dirty && (
          <Alert kind="warning" title="Modifications non téléchargées">
            Téléchargez le fichier avant de fermer l'application, puis rouvrez ce
            nouveau fichier au prochain contrôle.
          </Alert>
        )}

        {excel.hasFile && (
          <button type="button" className="btn btn-ghost block sm" onClick={open} disabled={excel.busy}>
            <FolderOpen size={16} aria-hidden="true" />
            Ouvrir un autre fichier
          </button>
        )}

        {rows.length > 0 && (
          <details className="fold">
            <summary>
              <Trash2 size={16} aria-hidden="true" />
              Supprimer un contrôle du fichier
              <ChevronDown size={18} className="chev" aria-hidden="true" />
            </summary>
            <div className="fold-body">
              <form
                className="delete-search"
                onSubmit={(e) => {
                  e.preventDefault()
                  setCriteria(search)
                }}
              >
                <span className="label">Rechercher un contrôle</span>
                <p className="hint">
                  Remplissez un ou plusieurs critères (les critères vides sont ignorés).
                </p>
                <div className="field">
                  <label htmlFor="search-date">Date</label>
                  <input
                    id="search-date"
                    type="date"
                    className="input"
                    value={search.date}
                    onChange={(e) => setSearch((s) => ({ ...s, date: e.target.value }))}
                  />
                </div>
                <div className="field">
                  <label htmlFor="search-controller">Contrôleur</label>
                  <input
                    id="search-controller"
                    className="input"
                    value={search.controller}
                    onChange={(e) => setSearch((s) => ({ ...s, controller: e.target.value }))}
                    placeholder="Nom ou partie du nom"
                  />
                </div>
                <div className="field">
                  <label htmlFor="search-branch">Agence</label>
                  <select
                    id="search-branch"
                    className="select"
                    value={search.branch}
                    onChange={(e) => setSearch((s) => ({ ...s, branch: e.target.value }))}
                  >
                    <option value="">Toutes les agences</option>
                    {agencies.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
                <button type="submit" className="btn btn-secondary block">
                  <Search size={17} aria-hidden="true" />
                  Rechercher
                </button>
              </form>

              {criteria &&
                (results.length === 0 ? (
                  <p className="hint">Aucun contrôle ne correspond à ces critères.</p>
                ) : (
                  <>
                    <p className="hint">
                      {plural(results.length, 'contrôle trouvé', 'contrôles trouvés')}
                      {results.length > SEARCH_MAX_RESULTS
                        ? ` — les ${SEARCH_MAX_RESULTS} plus récents sont affichés, précisez la recherche.`
                        : '.'}
                    </p>
                    <ul className="search-results">
                      {results.slice(0, SEARCH_MAX_RESULTS).map((r) => {
                        const problems = r.nb_problemes || '0'
                        return (
                          <li key={`${rowValue(r)}|${r.report_id}`}>
                            <div>
                              <strong>
                                {frDate(r.date_controle)} à {r.heure_controle || '—'}
                              </strong>
                              <span>
                                {r.agence || '—'} · {r.controleur || '—'} ·{' '}
                                {problems === '0' ? (
                                  <span className="ok">RAS</span>
                                ) : (
                                  <span className="bad">{plural(Number(problems), 'anomalie')}</span>
                                )}
                              </span>
                            </div>
                            <button
                              type="button"
                              className="btn btn-danger sm"
                              onClick={() => deleteRow(r)}
                              disabled={excel.busy}
                              aria-label={`Supprimer le contrôle du ${rowLabel(r)}`}
                            >
                              <Trash2 size={16} aria-hidden="true" />
                              Supprimer
                            </button>
                          </li>
                        )
                      })}
                    </ul>
                  </>
                ))}

              <hr className="divider" />

              <div className="field">
                <label htmlFor="delete-row">Ou choisissez le contrôle à supprimer</label>
                <select
                  id="delete-row"
                  className="select"
                  value={toDelete}
                  onChange={(e) => setToDelete(e.target.value)}
                >
                  <option value="">Choisissez un contrôle…</option>
                  {rows.map((r) => {
                    const value = rowValue(r)
                    return (
                      <option key={`${value}|${r.report_id}`} value={value}>
                        {rowLabel(r)}
                      </option>
                    )
                  })}
                </select>
              </div>
              <button
                type="button"
                className="btn btn-danger block"
                onClick={handleDelete}
                disabled={!toDelete || excel.busy}
              >
                <Trash2 size={17} aria-hidden="true" />
                Supprimer ce contrôle
              </button>
            </div>
          </details>
        )}
      </div>
    </Card>
  )
}
