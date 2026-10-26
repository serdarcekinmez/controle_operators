// Petites fonctions partagées : dates, noms de fichiers, encodage.

export const XLSX_MIME =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

const pad = (n) => String(n).padStart(2, '0')

export function todayIso() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function firstOfMonthIso() {
  return todayIso().slice(0, 8) + '01'
}

export function nowTime() {
  const d = new Date()
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** AAAA-MM-JJ -> JJ/MM/AAAA (texte laissé tel quel s'il est différent). */
export function frDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso || ''
}

/** Nom comparable : espaces superflus retirés, casse ignorée. */
export function normalizeName(name) {
  return (name || '').trim().split(/\s+/).join(' ').toLowerCase()
}

/**
 * Nom du fichier de contrôle téléchargé : « AAMMJJ - Prénom.xlsx »
 * (ex. « 261016 - Jean.xlsx », « 261016 - Controles.xlsx » sans nom).
 */
export function excelDownloadName(controller) {
  let first = (controller || '').trim().split(/\s+/)[0] || ''
  if (first && first === first.toLowerCase()) {
    first = first.replace(/(^|[-'])(\p{L})/gu, (_, sep, ch) => sep + ch.toUpperCase())
  }
  const clean = (part) => part.replace(/[\\/:*?"<>|\x00-\x1f]/g, '').replace(/^[ .]+|[ .]+$/g, '')
  const stamp = todayIso().slice(2).replaceAll('-', '')
  return [stamp, clean(first) || 'Controles'].join(' - ') + '.xlsx'
}

export function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`
}

export function bytesToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

export function base64ToBytes(text) {
  const binary = atob(text)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

/** Fait télécharger un fichier par le navigateur (dossier Téléchargements). */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

export function plural(n, word, wordPlural = word + 's') {
  return `${n} ${n > 1 ? wordPlural : word}`
}
