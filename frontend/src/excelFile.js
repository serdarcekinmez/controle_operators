// Accès direct au fichier de contrôle Excel sur le disque.
//
// Edge et Chrome savent ouvrir un fichier puis y réécrire directement
// (File System Access API) : le contrôleur n'a plus besoin de retélécharger
// son fichier après chaque contrôle. L'accès au dernier fichier est mémorisé
// dans le navigateur (IndexedDB) pour le reprendre en un clic la fois
// suivante. Les autres navigateurs (Firefox...) gardent le fonctionnement de
// la V3 : chargement du fichier, puis téléchargement de la version à jour.

import { XLSX_MIME } from './utils.js'

export const canWriteFiles =
  typeof window !== 'undefined' && 'showOpenFilePicker' in window && 'showSaveFilePicker' in window

const PICKER_TYPES = [
  { description: 'Fichier de contrôle Excel', accept: { [XLSX_MIME]: ['.xlsx'] } },
]

/** Choix du fichier existant. Retourne null si l'utilisateur annule. */
export async function pickExistingFile() {
  try {
    const [handle] = await window.showOpenFilePicker({
      types: PICKER_TYPES,
      excludeAcceptAllOption: true,
      startIn: 'downloads',
      id: 'controle-excel',
    })
    return handle
  } catch (err) {
    if (err?.name === 'AbortError') return null
    throw err
  }
}

/** Création d'un nouveau fichier. Retourne null si l'utilisateur annule. */
export async function pickNewFile(suggestedName) {
  try {
    return await window.showSaveFilePicker({
      types: PICKER_TYPES,
      excludeAcceptAllOption: true,
      suggestedName,
      startIn: 'documents',
      id: 'controle-excel',
    })
  } catch (err) {
    if (err?.name === 'AbortError') return null
    throw err
  }
}

/** Demande (ou vérifie) le droit d'écrire dans le fichier. */
export async function ensureWritePermission(handle) {
  const options = { mode: 'readwrite' }
  if ((await handle.queryPermission(options)) === 'granted') return true
  return (await handle.requestPermission(options)) === 'granted'
}

export async function readHandle(handle) {
  const file = await handle.getFile()
  return file.arrayBuffer()
}

export async function writeHandle(handle, bytes) {
  const writable = await handle.createWritable()
  try {
    await writable.write(bytes)
    await writable.close()
  } catch (err) {
    await writable.abort().catch(() => {})
    throw err
  }
}

// --- Mémorisation du dernier fichier (IndexedDB) -------------------------- //
const DB_NAME = 'controle-agences'
const STORE = 'handles'
const KEY = 'excel'

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function withStore(mode, action) {
  const db = await openDb()
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = action(tx.objectStore(STORE))
      tx.oncomplete = () => resolve(req?.result)
      tx.onerror = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}

export async function rememberHandle(handle) {
  try {
    await withStore('readwrite', (store) => store.put(handle, KEY))
  } catch {
    /* mémorisation facultative */
  }
}

export async function recallHandle() {
  if (!canWriteFiles) return null
  try {
    return (await withStore('readonly', (store) => store.get(KEY))) || null
  } catch {
    return null
  }
}

export async function forgetHandle() {
  try {
    await withStore('readwrite', (store) => store.delete(KEY))
  } catch {
    /* rien à oublier */
  }
}
