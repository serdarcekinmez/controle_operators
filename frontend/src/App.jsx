import { useEffect, useMemo, useState } from 'react'
import { ClipboardCheck, FileSpreadsheet, Power, Search } from 'lucide-react'
import { getJson, postForm } from './api.js'
import { useExcel } from './useExcel.js'
import { frDate, normalizeName, nowTime, plural, todayIso } from './utils.js'
import { Alert, Card, Chip, Spinner } from './components/ui.jsx'
import GeneralInfo from './components/GeneralInfo.jsx'
import Checklist from './components/Checklist.jsx'
import Documents from './components/Documents.jsx'
import ExcelPanel from './components/ExcelPanel.jsx'
import ReportPanel from './components/ReportPanel.jsx'
import Audit from './components/Audit.jsx'
import QuitDialog from './components/QuitDialog.jsx'

const CONTROLLER_KEY = 'controle-agences:controller'
const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png']

function storedController() {
  try {
    return localStorage.getItem(CONTROLLER_KEY) || ''
  } catch {
    return ''
  }
}

function emptyForm(controller) {
  return { controller, branch: '', date: todayIso(), time: nowTime(), observations: '' }
}

/** Erreurs du formulaire : par champ (surlignage) et messages complets. */
function validate(report, items, rows) {
  const fields = {}
  const messages = []
  const missing = []
  if (!report.controller) {
    fields.controller = 'Indiquez votre nom.'
    missing.push('le nom du contrôleur')
  }
  if (!report.branch) {
    fields.branch = "Choisissez l'agence contrôlée."
    missing.push("l'agence")
  }
  if (!report.control_date) {
    fields.date = 'Indiquez la date du contrôle.'
    missing.push('la date')
  }
  if (!report.control_time) {
    fields.time = "Indiquez l'heure du contrôle."
    missing.push("l'heure")
  }
  if (missing.length) messages.push(`Champs obligatoires manquants : ${missing.join(', ')}.`)

  const uncommented = items.filter(
    (i) => report.statuses[i.key] === 'problem' && !report.problem_comments[i.key]
  )
  for (const item of uncommented) fields[`comment_${item.key}`] = "Décrivez l'anomalie constatée."
  if (uncommented.length) {
    messages.push(
      'Un commentaire est obligatoire pour chaque anomalie signalée : ' +
        uncommented.map((i) => i.label).join(', ') + '.'
    )
  }

  // Date + heure + contrôleur identifient un contrôle dans le fichier Excel.
  if (!missing.length) {
    const clash = rows.find(
      (r) =>
        r.date_controle === report.control_date &&
        r.heure_controle === report.control_time &&
        normalizeName(r.controleur) === normalizeName(report.controller) &&
        r.agence !== report.branch
    )
    if (clash) {
      fields.time = 'Heure déjà utilisée par un autre de vos contrôles.'
      messages.push(
        `Le fichier Excel contient déjà un contrôle de ${report.controller} le ` +
          `${frDate(report.control_date)} à ${report.control_time} (agence ${clash.agence}). ` +
          "Corrigez l'heure du contrôle."
      )
    }
  }
  return { fields, messages }
}

function focusFirstError(fields, items) {
  const order = ['controller', 'branch', 'date', 'time', ...items.map((i) => `comment_${i.key}`)]
  const id = order.find((key) => fields[key])
  const el = id && document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus({ preventScroll: true })
  }
}

let nextDocId = 1

export default function App() {
  const [config, setConfig] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [tab, setTab] = useState('control')
  const [form, setForm] = useState(() => emptyForm(storedController()))
  const [statuses, setStatuses] = useState({})
  const [comments, setComments] = useState({})
  const [docs, setDocs] = useState([])
  const [attempted, setAttempted] = useState(false)
  const [report, setReport] = useState(null)
  const [reportBusy, setReportBusy] = useState(false)
  const [reportMsg, setReportMsg] = useState(null)
  const [savedSignature, setSavedSignature] = useState(null)
  const [reportCount, setReportCount] = useState(0)
  const [quitOpen, setQuitOpen] = useState(false)
  const [closed, setClosed] = useState(false)
  const excel = useExcel()

  useEffect(() => {
    getJson('/api/config')
      .then((cfg) => {
        setConfig(cfg)
        setForm((f) => (f.controller ? f : { ...f, controller: cfg.default_controller }))
      })
      .catch((err) => setLoadError(err.message))
  }, [])

  // Le nom du contrôleur est retenu d'une fois sur l'autre.
  useEffect(() => {
    try {
      if (form.controller.trim()) localStorage.setItem(CONTROLLER_KEY, form.controller.trim())
    } catch {
      /* mémorisation facultative */
    }
  }, [form.controller])

  // Avertit avant de fermer la page si le fichier Excel n'est pas sauvegardé
  // (sauf une fois l'application quittée : la question a déjà été posée).
  useEffect(() => {
    if (!excel.dirty || closed) return undefined
    const warn = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [excel.dirty, closed])

  const items = useMemo(() => config?.control_items || [], [config])

  const payload = useMemo(
    () => ({
      controller: form.controller.trim(),
      branch: form.branch,
      control_date: form.date,
      control_time: form.time,
      statuses: Object.fromEntries(items.map((i) => [i.key, statuses[i.key] || ''])),
      problem_comments: Object.fromEntries(
        items
          .filter((i) => statuses[i.key] === 'problem')
          .map((i) => [i.key, (comments[i.key] || '').trim()])
      ),
      observations: form.observations,
    }),
    [form, statuses, comments, items]
  )
  const signature = JSON.stringify(payload)
  const pdfSignature = `${signature}|${docs.map((d) => d.id).join(',')}`
  const validation = useMemo(() => validate(payload, items, excel.rows), [payload, items, excel.rows])
  const shownErrors = attempted ? validation.fields : {}

  const setField = (name, value) => setForm((f) => ({ ...f, [name]: value }))

  const toggleStatus = (key, value) =>
    setStatuses((s) => ({ ...s, [key]: s[key] === value ? '' : value }))

  const ensureValid = () => {
    setAttempted(true)
    if (!validation.messages.length) return true
    focusFirstError(validation.fields, items)
    return false
  }

  // --- Documents scannés : vérifiés dès l'ajout ---------------------------- //
  const addDocs = (files) => {
    const added = files.map((file) => {
      const ext = file.name.split('.').pop().toLowerCase()
      const allowed = config.upload_extensions.includes(ext)
      return {
        id: nextDocId++,
        file,
        kind: IMAGE_EXTENSIONS.includes(ext) ? 'image' : 'pdf',
        status: allowed ? 'checking' : 'error',
        message: allowed ? '' : 'Format non accepté (PDF, JPG, JPEG ou PNG) : il sera ignoré.',
      }
    })
    setDocs((list) => [...list, ...added])
    for (const doc of added.filter((d) => d.status === 'checking')) {
      const data = new FormData()
      data.append('file', doc.file, doc.file.name)
      postForm('/api/attachments/check', data)
        .then((res) => ({ status: res.ok ? 'ok' : 'error', kind: res.kind || doc.kind, pages: res.pages, message: res.error || '' }))
        .catch((err) => ({ status: 'error', message: err.message }))
        .then((changes) => setDocs((list) => list.map((d) => (d.id === doc.id ? { ...d, ...changes } : d))))
    }
  }

  // --- Actions ------------------------------------------------------------ //
  const saveToExcel = async () => {
    if (!ensureValid()) {
      excel.setMessage({ kind: 'error', text: validation.messages.join(' ') })
      return
    }
    if (await excel.save(payload)) setSavedSignature(signature)
  }

  const createReport = async () => {
    if (!ensureValid()) {
      setReportMsg({ kind: 'error', text: validation.messages.join(' ') })
      return
    }
    setReportBusy(true)
    setReportMsg(null)
    try {
      const data = new FormData()
      data.append('data', JSON.stringify(payload))
      for (const doc of docs) {
        if (doc.status !== 'error') data.append('files', doc.file, doc.file.name)
      }
      const res = await postForm('/api/report', data)
      const skipped = docs
        .filter((d) => d.status === 'error')
        .map((d) => `Document non joint (illisible ou format refusé) : ${d.file.name}`)
      setReport({ ...res, warnings: [...skipped, ...res.warnings], signature: pdfSignature })
      setReportCount((n) => n + 1)
      if (await excel.save(res.report)) setSavedSignature(signature)
    } catch (err) {
      setReportMsg({ kind: 'error', text: err.message })
    } finally {
      setReportBusy(false)
    }
  }

  const newControl = () => {
    if (
      savedSignature !== signature &&
      !window.confirm("Ce contrôle n'est pas enregistré dans Excel. Commencer quand même un nouveau contrôle ?")
    ) {
      return
    }
    setForm(emptyForm(form.controller))
    setStatuses({})
    setComments({})
    setDocs([])
    setReport(null)
    setReportMsg(null)
    setAttempted(false)
    setSavedSignature(null)
    excel.setMessage(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // --- Écrans d'attente / d'erreur / de fermeture ------------------------- //
  if (closed) {
    return (
      <div className="container" style={{ paddingTop: 48, maxWidth: 720 }}>
        <Alert kind="success" title="L'application est fermée">
          Vous pouvez fermer cet onglet du navigateur. Pour la rouvrir :
          double-cliquez sur RUN_APP.bat (ou l'icône du Bureau).
        </Alert>
      </div>
    )
  }
  if (loadError) {
    return (
      <div className="container" style={{ paddingTop: 48, maxWidth: 720 }}>
        <Alert kind="error" title="L'application n'a pas pu démarrer">
          {loadError}
        </Alert>
      </div>
    )
  }
  if (!config) {
    return (
      <div className="loading-screen">
        <Spinner size={32} />
        Chargement de l'application…
      </div>
    )
  }

  // --- État d'avancement (panneau « Finaliser le contrôle ») -------------- //
  const f = validation.fields
  const infoOk = !f.controller && !f.branch && !f.date && !f.time
  const answered = items.filter((i) => statuses[i.key]).length
  const problems = items.filter((i) => statuses[i.key] === 'problem').length
  const uncommented = items.filter((i) => f[`comment_${i.key}`]).length
  const goodDocs = docs.filter((d) => d.status === 'ok').length
  const badDocs = docs.filter((d) => d.status === 'error').length
  const reportView = report && { ...report, stale: report.signature !== pdfSignature }
  const saved = savedSignature === signature

  const status = [
    {
      label: 'Informations générales',
      level: infoOk ? 'ok' : attempted ? 'bad' : 'todo',
      value: infoOk ? 'Complètes' : 'À compléter',
    },
    {
      label: 'Points renseignés',
      level: answered === items.length ? 'ok' : answered ? 'warn' : 'todo',
      value: `${answered}/${items.length}`,
    },
    {
      label: 'Anomalies',
      level: problems ? 'bad' : answered ? 'ok' : 'todo',
      value: problems
        ? `${problems}${uncommented ? ` · ${plural(uncommented, 'commentaire')} manquant${uncommented > 1 ? 's' : ''}` : ''}`
        : answered ? 'Aucune' : '—',
    },
    {
      label: 'Documents scannés',
      level: badDocs ? 'warn' : goodDocs ? 'ok' : 'todo',
      value: badDocs ? `${plural(badDocs, 'illisible')}` : goodDocs ? plural(goodDocs, 'document') : 'Aucun',
    },
    {
      label: 'Rapport PDF',
      level: reportView ? (reportView.stale ? 'warn' : 'ok') : 'todo',
      value: reportView ? (reportView.stale ? 'À recréer' : 'Créé') : 'Pas encore créé',
    },
    {
      label: 'Fichier Excel',
      level: saved ? (!excel.handle && excel.dirty ? 'warn' : 'ok') : excel.hasFile ? 'todo' : 'warn',
      value: saved
        ? !excel.handle && excel.dirty ? 'À télécharger' : 'Enregistré'
        : excel.hasFile ? 'Pas encore enregistré' : 'Aucun fichier ouvert',
    },
  ]

  const excelChip = !excel.hasFile ? (
    <Chip kind="warning" icon={FileSpreadsheet} onClick={() => { setTab('control'); setTimeout(() => document.getElementById('excel')?.scrollIntoView({ behavior: 'smooth' }), 0) }}>
      Aucun fichier Excel ouvert
    </Chip>
  ) : excel.handle && !excel.writeFailed ? (
    <Chip kind="success" icon={FileSpreadsheet} title="Les contrôles sont enregistrés directement dans ce fichier">
      {excel.name}
    </Chip>
  ) : excel.dirty ? (
    <Chip kind="warning" icon={FileSpreadsheet}>
      Fichier Excel à télécharger
    </Chip>
  ) : (
    <Chip kind="info" icon={FileSpreadsheet}>
      {excel.name || 'Nouveau fichier'}
    </Chip>
  )

  return (
    <>
      <header className="app-header">
        <div className="container">
          <div className="header-top">
            <img className="brand-logo" src="/logo_interchange.png" alt="Interchange" />
            <div className="brand-text">
              <h1>{config.title}</h1>
              <p>{config.subtitle}</p>
            </div>
            <div className="header-status">{excelChip}</div>
            <button type="button" className="btn btn-ghost sm header-quit" onClick={() => setQuitOpen(true)}>
              <Power size={16} aria-hidden="true" /> Quitter l'application
            </button>
          </div>
          <nav className="tabs" role="tablist" aria-label="Sections">
            <button type="button" role="tab" className="tab" aria-selected={tab === 'control'} onClick={() => setTab('control')}>
              <ClipboardCheck size={18} aria-hidden="true" /> Nouveau contrôle
            </button>
            <button type="button" role="tab" className="tab" aria-selected={tab === 'audit'} onClick={() => setTab('audit')}>
              <Search size={18} aria-hidden="true" /> Consultation des rapports
            </button>
          </nav>
        </div>
      </header>

      <main className="container app-main">
        <div hidden={tab !== 'control'}>
          <div className="layout">
            <div className="stack">
              <GeneralInfo
                form={form}
                setField={setField}
                branches={config.branches}
                errors={shownErrors}
                done={infoOk}
              />
              <Checklist
                items={items}
                statuses={statuses}
                comments={comments}
                onStatus={toggleStatus}
                onComment={(key, value) => setComments((c) => ({ ...c, [key]: value }))}
                errors={shownErrors}
              />
              <div className="grid-2">
                <Card id="observations" step={3} title="Observations générales" subtitle="Facultatif — remarques sur l'ensemble du contrôle.">
                  <label htmlFor="observations-text" className="sr-only">
                    Observations générales
                  </label>
                  <textarea
                    id="observations-text"
                    className="textarea"
                    style={{ minHeight: 160 }}
                    value={form.observations}
                    onChange={(e) => setField('observations', e.target.value)}
                    placeholder="Remarques générales sur le contrôle…"
                  />
                </Card>
                <Documents
                  docs={docs}
                  onAdd={addDocs}
                  onRemove={(id) => setDocs((list) => list.filter((d) => d.id !== id))}
                  extensions={config.upload_extensions}
                />
              </div>
            </div>

            <aside className="aside" aria-label="Finalisation">
              <div className="stack">
                <ReportPanel
                  status={status}
                  busy={reportBusy}
                  message={reportMsg}
                  onClearMessage={() => setReportMsg(null)}
                  report={reportView}
                  onCreate={createReport}
                  onNew={newControl}
                />
                <ExcelPanel
                  excel={excel}
                  controller={form.controller}
                  branches={config.branches}
                  onSave={saveToExcel}
                  saved={saved}
                />
              </div>
            </aside>
          </div>
        </div>

        <div hidden={tab !== 'audit'}>
          <Audit config={config} excel={excel} historyKey={reportCount} />
        </div>
      </main>

      <QuitDialog
        open={quitOpen}
        unsaved={excel.dirty}
        onCancel={() => setQuitOpen(false)}
        onQuit={() => {
          setQuitOpen(false)
          setClosed(true)
        }}
      />

      <footer className="app-footer">
        Application locale — aucune donnée client n'est enregistrée, rien ne quitte ce poste.
      </footer>
    </>
  )
}
