import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, ExternalLink, FileSpreadsheet, History, Plus, Printer, Trash2 } from 'lucide-react'
import { getJson, postJson, postJsonForBlob } from '../api.js'
import {
  XLSX_MIME,
  bytesToBase64,
  downloadBlob,
  firstOfMonthIso,
  frDate,
  plural,
  todayIso,
} from '../utils.js'
import { Alert, Card, Chip, Spinner } from './ui.jsx'

// Colonnes affichées à l'écran (toutes les colonnes restent dans les exports).
const DISPLAY_COLUMNS = [
  'date_controle',
  'heure_controle',
  'agence',
  'controleur',
  'journee_comptable',
  'caisses',
  'acr',
  'affichage',
  'cash',
  'nb_problemes',
  'observations',
]

const SCOPES = [
  ['one', 'Une agence'],
  ['several', 'Plusieurs agences'],
  ['all', 'Toutes les agences'],
]

function cellInfo(column, value, config) {
  let text = String(value ?? '')
  if (column === 'date_controle') text = frDate(text)
  if (column === 'nb_problemes') return { cls: `num${text && text !== '0' ? ' hot' : ''}`, text }
  if (text === config.value_ok) return { cls: 'ras', text }
  if (config.problem_prefixes.some((p) => text.startsWith(p))) return { cls: 'pb', text }
  if (!text) return { cls: 'na', text: '—' }
  return { cls: column === 'date_controle' || column === 'heure_controle' ? 'nowrap' : '', text }
}

const escapeHtml = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])

/** Document HTML autonome, téléchargeable et imprimable. */
function buildHtmlDocument(rows, subtitle, config) {
  const columns = config.sheet_columns
  const head = columns.map((c) => `<th>${escapeHtml(config.column_labels[c] || c)}</th>`).join('')
  const body = rows
    .map(
      (row) =>
        '<tr>' +
        columns
          .map((c) => {
            const { cls, text } = cellInfo(c, row[c], config)
            return `<td class="${cls}">${escapeHtml(text)}</td>`
          })
          .join('') +
        '</tr>'
    )
    .join('')
  const now = new Date()
  const generated = `${frDate(todayIso())} à ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  return `<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Rapports de contrôle niveau 1</title>
<style>
body { font-family: 'Segoe UI', system-ui, Arial, sans-serif; margin: 2rem; color: #0f1f33; }
h1 { color: #0b2a4a; margin-bottom: .2rem; }
p.meta { color: #56677d; font-size: .85rem; margin-top: 0; }
table { border-collapse: collapse; width: 100%; font-size: .8rem; }
th { background: #0b2a4a; color: #fff; text-align: left; padding: .45rem .6rem; white-space: nowrap; }
td { padding: .4rem .6rem; border-top: 1px solid #e6ecf4; vertical-align: top; }
tbody tr:nth-child(even) { background: #f7f9fc; }
td.ras { color: #157a3c; font-weight: 600; }
td.pb { color: #c42b1c; font-weight: 600; }
td.na { color: #8796aa; }
td.num { text-align: center; font-weight: 700; }
td.num.hot { color: #c42b1c; }
td.nowrap { white-space: nowrap; }
</style></head><body>
<h1>Rapports de contrôle niveau 1</h1>
<p class="meta">${escapeHtml(subtitle)} — ${rows.length} rapport(s) — édité le ${generated}</p>
<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
</body></html>`
}

function HistoryCard({ refreshKey }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getJson('/api/history')
      .then((res) => setItems(res.items))
      .catch((err) => setError(err.message))
  }, [refreshKey])

  return (
    <Card title="Derniers rapports créés sur ce poste" subtitle="Les PDF sont conservés dans le dossier « reports » de l'application.">
      {error && <Alert kind="error">{error}</Alert>}
      {!items && !error && <Spinner />}
      {items && items.length === 0 && <div className="empty">Aucun rapport créé pour le moment.</div>}
      {items && items.length > 0 && (
        <ul className="history-list">
          {items.map((item, idx) => (
            <li key={`${item.report_id}-${idx}`}>
              <History size={20} aria-hidden="true" style={{ color: 'var(--blue)', flexShrink: 0 }} />
              <div className="h-main">
                <strong>{item.branch}</strong>
                <span>
                  {frDate(item.control_date)} · {item.controller}
                </span>
              </div>
              {item.has_pdf && item.report_id ? (
                <a className="btn btn-secondary sm" href={`/api/reports/${item.report_id}`} target="_blank" rel="noreferrer">
                  <ExternalLink size={16} aria-hidden="true" /> Ouvrir
                </a>
              ) : (
                <Chip kind="neutral">PDF introuvable</Chip>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export default function Audit({ config, excel, historyKey }) {
  const inputRef = useRef(null)
  const [extras, setExtras] = useState([]) // [{name, data}]
  const [allRows, setAllRows] = useState([])
  const [warnings, setWarnings] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [scope, setScope] = useState('all')
  const [oneBranch, setOneBranch] = useState('')
  const [several, setSeveral] = useState([])
  const [from, setFrom] = useState(firstOfMonthIso())
  const [to, setTo] = useState(todayIso())
  const [exporting, setExporting] = useState(false)

  const ownName = excel.name || (excel.workbook ? 'fichier de cette séance' : null)

  // Relecture des fichiers dès qu'un fichier est ajouté / retiré / modifié.
  useEffect(() => {
    const sources = [...extras]
    if (excel.workbook) sources.push({ name: ownName, data: excel.workbook })
    if (!sources.length) {
      setAllRows([])
      setWarnings([])
      return
    }
    let cancelled = false
    setLoading(true)
    setError('')
    postJson('/api/audit', { sources })
      .then((res) => {
        if (cancelled) return
        setAllRows(res.rows)
        setWarnings(res.warnings)
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [extras, excel.workbook, ownName])

  const selected = scope === 'one' ? (oneBranch ? [oneBranch] : []) : scope === 'several' ? several : []
  const needsBranch = scope !== 'all' && selected.length === 0
  const badPeriod = from && to && from > to

  const rows = useMemo(() => {
    if (needsBranch || badPeriod) return []
    return allRows.filter(
      (row) =>
        (!from || row.date_controle >= from) &&
        (!to || row.date_controle <= to) &&
        (scope === 'all' || selected.includes(row.agence))
    )
  }, [allRows, from, to, scope, selected, needsBranch, badPeriod])

  const problems = rows.filter((r) => (r.nb_problemes || '0') !== '0').length
  const agencies = new Set(rows.map((r) => r.agence)).size
  const scopeLabel = scope === 'all' ? 'Toutes les agences' : selected.join(', ')
  const subtitle = `${scopeLabel} — du ${frDate(from)} au ${frDate(to)}`
  const stamp = todayIso().replaceAll('-', '')

  const addFiles = async (fileList) => {
    const added = await Promise.all(
      Array.from(fileList).map(async (f) => ({ name: f.name, data: bytesToBase64(await f.arrayBuffer()) }))
    )
    setExtras((prev) => [...prev.filter((p) => !added.some((a) => a.name === p.name)), ...added])
  }

  const exportExcel = async () => {
    setExporting(true)
    try {
      const blob = await postJsonForBlob('/api/excel/export', { rows })
      downloadBlob(new Blob([blob], { type: XLSX_MIME }), `rapports_controle_n1_${stamp}.xlsx`)
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  const exportHtml = () => {
    const html = buildHtmlDocument(rows, subtitle, config)
    downloadBlob(new Blob([html], { type: 'text/html;charset=utf-8' }), `rapports_controle_n1_${stamp}.html`)
  }

  return (
    <div className="stack">
      <Card
        title="Consultation des rapports"
        subtitle="Recherchez dans les fichiers de contrôle Excel, par agence et par période. Les résultats se mettent à jour automatiquement."
      >
        <div className="section-gap">
          <div>
            <span className="label">Fichiers consultés</span>
            <div className="btn-row" style={{ marginTop: 8, alignItems: 'center' }}>
              {ownName ? (
                <Chip kind="success" icon={FileSpreadsheet}>
                  Votre fichier : {ownName}
                </Chip>
              ) : (
                <Chip kind="warning" icon={FileSpreadsheet}>
                  Votre fichier n'est pas ouvert (onglet « Nouveau contrôle »)
                </Chip>
              )}
              {extras.map((x) => (
                <Chip key={x.name} kind="info" icon={Trash2} onClick={() => setExtras((p) => p.filter((e) => e.name !== x.name))} title="Retirer ce fichier">
                  {x.name}
                </Chip>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <button type="button" className="btn btn-secondary sm" onClick={() => inputRef.current?.click()}>
                <Plus size={16} aria-hidden="true" /> Ajouter les fichiers d'autres contrôleurs
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx"
                multiple
                hidden
                onChange={(e) => {
                  addFiles(e.target.files)
                  e.target.value = ''
                }}
              />
              <p className="hint" style={{ marginTop: 6 }}>
                Ils sont seulement lus, jamais modifiés. Un contrôle présent dans plusieurs fichiers n'est compté qu'une fois.
              </p>
            </div>
          </div>

          <hr className="divider" />

          <div className="filters">
            <div className="field">
              <span className="label">Périmètre</span>
              <div className="pill-group" role="group" aria-label="Périmètre">
                {SCOPES.map(([value, label]) => (
                  <button key={value} type="button" className="pill" aria-pressed={scope === value} onClick={() => setScope(value)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label htmlFor="from">Du</label>
              <input id="from" type="date" className={`input${badPeriod ? ' invalid' : ''}`} value={from} onChange={(e) => setFrom(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="to">Au</label>
              <input id="to" type="date" className={`input${badPeriod ? ' invalid' : ''}`} value={to} onChange={(e) => setTo(e.target.value)} />
            </div>
          </div>

          {scope === 'one' && (
            <div className="field" style={{ maxWidth: 360 }}>
              <label htmlFor="one-branch">Agence</label>
              <select id="one-branch" className="select" value={oneBranch} onChange={(e) => setOneBranch(e.target.value)}>
                <option value="">Choisissez une agence…</option>
                {config.branches.map((b) => (
                  <option key={b}>{b}</option>
                ))}
              </select>
            </div>
          )}

          {scope === 'several' && (
            <div className="field">
              <span className="label">Agences</span>
              <div className="branch-grid">
                {config.branches.map((b) => (
                  <label key={b} className="branch-check">
                    <input
                      type="checkbox"
                      checked={several.includes(b)}
                      onChange={(e) => setSeveral((p) => (e.target.checked ? [...p, b] : p.filter((x) => x !== b)))}
                    />
                    {b}
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>

      <Card
        title="Résultats"
        subtitle={subtitle}
        extra={loading ? <Spinner /> : null}
      >
        <div className="section-gap">
          {error && <Alert kind="error">{error}</Alert>}
          {warnings.map((w) => (
            <Alert key={w} kind="warning">
              {w}
            </Alert>
          ))}

          {needsBranch ? (
            <Alert kind="warning">Sélectionnez au moins une agence.</Alert>
          ) : badPeriod ? (
            <Alert kind="error">La date de début est postérieure à la date de fin.</Alert>
          ) : allRows.length === 0 && !loading ? (
            <div className="empty">
              Aucun contrôle à consulter : ouvrez votre fichier de contrôle Excel, ou ajoutez des fichiers ci-dessus.
            </div>
          ) : rows.length === 0 && !loading ? (
            <div className="empty">Aucun rapport ne correspond à ces critères.</div>
          ) : (
            rows.length > 0 && (
              <>
                <div className="metrics">
                  <div className="metric">
                    <div className="metric-label">Rapports</div>
                    <div className="metric-value">{rows.length}</div>
                  </div>
                  <div className={`metric ${problems ? 'bad' : 'good'}`}>
                    <div className="metric-label">Avec anomalie</div>
                    <div className="metric-value">{problems}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">Agences couvertes</div>
                    <div className="metric-value">{agencies}</div>
                  </div>
                </div>

                <div className="table-wrap">
                  <table className="audit">
                    <thead>
                      <tr>
                        {DISPLAY_COLUMNS.map((c) => (
                          <th key={c}>{config.column_labels[c] || c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, idx) => (
                        <tr key={`${row.report_id}-${idx}`}>
                          {DISPLAY_COLUMNS.map((c) => {
                            const { cls, text } = cellInfo(c, row[c], config)
                            return (
                              <td key={c} className={cls}>
                                {text}
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="btn-row">
                  <button type="button" className="btn btn-secondary" onClick={exportHtml}>
                    <Printer size={18} aria-hidden="true" /> Télécharger en HTML (impression)
                  </button>
                  <button type="button" className="btn btn-secondary" onClick={exportExcel} disabled={exporting}>
                    {exporting ? <Spinner /> : <Download size={18} aria-hidden="true" />} Télécharger en Excel
                  </button>
                </div>
                <p className="hint">{plural(rows.length, 'rapport')} affiché{rows.length > 1 ? 's' : ''}.</p>
              </>
            )
          )}
        </div>
      </Card>

      <HistoryCard refreshKey={historyKey} />
    </div>
  )
}
