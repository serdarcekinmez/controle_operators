// État du fichier de contrôle Excel du contrôleur.
//
// Comme dans la V3, le classeur à jour = fichier chargé + contrôles
// enregistrés pendant la séance - contrôles supprimés. Le serveur fait le
// calcul (services/excel_service.py) ; ce module garde les trois éléments.
//
// Avec un accès direct au fichier (Edge / Chrome), le fichier est relu sur le
// disque avant chaque opération puis réécrit aussitôt : il est toujours à
// jour, et les notes ajoutées entre-temps dans Excel sont conservées.

import { useCallback, useEffect, useRef, useState } from 'react'
import { postJson } from './api.js'
import {
  canWriteFiles,
  ensureWritePermission,
  pickExistingFile,
  pickNewFile,
  readHandle,
  recallHandle,
  rememberHandle,
  writeHandle,
} from './excelFile.js'
import {
  XLSX_MIME,
  base64ToBytes,
  bytesToBase64,
  downloadBlob,
  excelDownloadName,
  frDate,
  plural,
} from './utils.js'

const EMPTY = {
  handle: null, // accès direct au fichier (Edge / Chrome)
  name: null, // nom du fichier ouvert ou créé
  base: null, // contenu du fichier chargé (base64), sans accès direct
  created: false, // nouveau fichier demandé, sans accès direct
  sessionRows: [], // contrôles enregistrés pendant la séance
  deleted: [], // contrôles supprimés pendant la séance
  workbook: null, // classeur à jour (base64)
  rows: [],
  baseCount: 0,
  total: 0,
  last: '',
  dirty: false, // modifications ni écrites dans le fichier, ni téléchargées
  writeFailed: false,
}

const LOCKED_HINT =
  'Le fichier est peut-être ouvert dans Excel : fermez-le, puis cliquez sur « Réessayer ».'

export function useExcel() {
  const ref = useRef(EMPTY)
  const [state, setState] = useState(EMPTY)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [message, setMessage] = useState(null)
  const [recalled, setRecalled] = useState(null)

  const patch = useCallback((changes) => {
    ref.current = { ...ref.current, ...changes }
    setState(ref.current)
  }, [])

  /** Recalcule le classeur côté serveur, puis l'écrit dans le fichier si besoin. */
  const compute = useCallback(
    async (endpoint, extra = {}, write = false) => {
      const cur = ref.current
      let base = cur.base
      if (cur.handle) {
        try {
          base = bytesToBase64(await readHandle(cur.handle))
        } catch {
          throw new Error(
            `Impossible de lire votre fichier « ${cur.name} » : il a peut-être été ` +
              'déplacé, renommé ou supprimé. Rouvrez-le avec « Ouvrir mon fichier ».'
          )
        }
      }
      const res = await postJson(endpoint, {
        base,
        session_rows: cur.sessionRows,
        deleted: cur.deleted,
        create: cur.created || Boolean(cur.handle),
        ...extra,
      })
      const changes = {
        base: cur.handle ? null : base,
        sessionRows: res.session_rows,
        deleted: res.deleted,
        workbook: res.workbook,
        rows: res.rows,
        baseCount: res.base_count,
        total: res.total,
        last: res.last,
      }
      if (write && cur.handle && res.workbook) {
        try {
          await writeHandle(cur.handle, base64ToBytes(res.workbook))
          Object.assign(changes, { dirty: false, writeFailed: false })
        } catch {
          Object.assign(changes, { dirty: true, writeFailed: true })
        }
      } else if (write) {
        changes.dirty = true
      }
      patch(changes)
      return res
    },
    [patch]
  )

  /** Une seule opération à la fois ; les erreurs deviennent un message rouge. */
  const run = useCallback(async (action) => {
    if (busyRef.current) return null
    busyRef.current = true
    setBusy(true)
    try {
      return await action()
    } catch (err) {
      setMessage({ kind: 'error', text: err.message })
      return null
    } finally {
      busyRef.current = false
      setBusy(false)
    }
  }, [])

  const writtenNote = () => {
    const cur = ref.current
    if (cur.handle && cur.writeFailed) return null
    return cur.handle
      ? `Votre fichier « ${cur.name} » est à jour.`
      : 'Téléchargez le fichier pour conserver la mise à jour.'
  }

  const showWriteResult = (text) => {
    const cur = ref.current
    if (cur.handle && cur.writeFailed) {
      setMessage({
        kind: 'warning',
        text: `${text} Mais il n'a pas pu être écrit dans « ${cur.name} ». ${LOCKED_HINT}`,
      })
    } else {
      setMessage({ kind: 'success', text: `${text} ${writtenNote()}` })
    }
  }

  /** Branche un fichier (accès direct ou contenu chargé) et relit son contenu. */
  const attach = useCallback(
    async (changes, successText, forceWrite = false) => {
      const previous = ref.current
      // Les contrôles déjà écrits dans l'ancien fichier n'ont pas à suivre ;
      // sinon (pas encore téléchargés), ils sont ajoutés au nouveau fichier.
      const carry = !(previous.handle && !previous.dirty)
      patch({
        ...changes,
        sessionRows: carry ? previous.sessionRows : [],
        deleted: carry ? previous.deleted : [],
        dirty: false,
        writeFailed: false,
      })
      const pending = ref.current.sessionRows.length + ref.current.deleted.length
      try {
        await compute('/api/excel/state', {}, forceWrite || pending > 0)
      } catch (err) {
        patch({ ...previous })
        throw err
      }
      const cur = ref.current
      let text = successText(cur)
      if (pending && cur.sessionRows.length) {
        text += ` Les contrôles de cette séance (${cur.sessionRows.length}) y ont été ajoutés.`
      }
      if (cur.handle && cur.writeFailed) {
        setMessage({ kind: 'warning', text: `${text} ${LOCKED_HINT}` })
      } else {
        setMessage({ kind: 'success', text })
      }
    },
    [compute, patch]
  )

  const openedText = (cur) =>
    `Fichier « ${cur.name} » ouvert : ${plural(cur.baseCount, 'contrôle')}.` +
    (cur.handle ? ' Vos prochains contrôles y seront enregistrés directement.' : '')

  const openHandle = useCallback(
    async (handle) => {
      if (!(await ensureWritePermission(handle))) {
        // Lecture seule : on retombe sur le chargement classique.
        const base = bytesToBase64(await readHandle(handle))
        await attach({ handle: null, name: handle.name, base, created: false }, (cur) =>
          `${openedText(cur)} L'écriture directe a été refusée : téléchargez le fichier après chaque contrôle.`
        )
        return
      }
      await attach({ handle, name: handle.name, base: null, created: false }, openedText)
      await rememberHandle(handle)
      setRecalled(handle)
    },
    [attach]
  )

  // Au démarrage : proposer (ou rouvrir directement) le dernier fichier utilisé.
  useEffect(() => {
    let cancelled = false
    recallHandle().then(async (handle) => {
      if (cancelled || !handle) return
      setRecalled(handle)
      try {
        if ((await handle.queryPermission({ mode: 'readwrite' })) === 'granted') {
          await run(() => openHandle(handle))
        }
      } catch {
        /* l'utilisateur rouvrira le fichier lui-même */
      }
    })
    return () => {
      cancelled = true
    }
  }, [openHandle, run])

  // --- Actions exposées à l'interface ------------------------------------ //
  const openFile = () =>
    run(async () => {
      const handle = await pickExistingFile()
      if (handle) await openHandle(handle)
    })

  const resume = () => run(() => openHandle(recalled))

  const openFromInput = (file) =>
    run(async () => {
      const base = bytesToBase64(await file.arrayBuffer())
      await attach({ handle: null, name: file.name, base, created: false }, openedText)
    })

  const createNew = (controller) =>
    run(async () => {
      if (canWriteFiles) {
        const handle = await pickNewFile(excelDownloadName(controller))
        if (!handle) return
        await attach(
          { handle, name: handle.name, base: null, created: false },
          (cur) => `Nouveau fichier « ${cur.name} » créé. Vos contrôles y seront enregistrés directement.`,
          true
        )
        await rememberHandle(handle)
        setRecalled(handle)
      } else {
        await attach({ handle: null, name: null, base: null, created: true }, () =>
          'Nouveau fichier de contrôle créé. Enregistrez-y vos contrôles, puis téléchargez-le.'
        )
      }
    })

  /** Ajoute (ou met à jour) un contrôle. Retourne la ligne enregistrée. */
  const save = (report, { announce = true } = {}) =>
    run(async () => {
      const res = await compute('/api/excel/save', { report }, true)
      const row = res.row
      if (announce) {
        showWriteResult(
          `Contrôle enregistré : ${row.agence} — ${frDate(row.date_controle)} à ` +
            `${row.heure_controle} — ${row.controleur}.`
        )
      }
      return { row, written: Boolean(ref.current.handle && !ref.current.writeFailed) }
    })

  const remove = ({ date, time, controller }) =>
    run(async () => {
      const res = await compute('/api/excel/delete', { date, time, controller }, true)
      const agencies = [...new Set(res.removed.map((r) => r.agence))].join(', ')
      showWriteResult(`Contrôle supprimé : ${agencies} — ${frDate(date)} à ${time} — ${controller}.`)
      return true
    })

  const retryWrite = () =>
    run(async () => {
      await compute('/api/excel/state', {}, true)
      if (ref.current.writeFailed) {
        setMessage({ kind: 'warning', text: `Toujours impossible d'écrire dans « ${ref.current.name} ». ${LOCKED_HINT}` })
      } else {
        setMessage({ kind: 'success', text: `Votre fichier « ${ref.current.name} » est à jour.` })
      }
    })

  const download = (controller) => {
    const cur = ref.current
    if (!cur.workbook) return
    downloadBlob(
      new Blob([base64ToBytes(cur.workbook)], { type: XLSX_MIME }),
      excelDownloadName(controller)
    )
    patch({ dirty: cur.handle ? cur.dirty : false })
  }

  return {
    ...state,
    busy,
    message,
    setMessage,
    recalled,
    canWriteFiles,
    hasFile: Boolean(state.handle || state.name || state.created),
    openFile,
    resume,
    openFromInput,
    createNew,
    save,
    remove,
    retryWrite,
    download,
  }
}
