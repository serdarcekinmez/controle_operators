// Appels au serveur Python local. Chaque erreur est remontée avec le message
// en français renvoyé par le serveur (champ « error »).

const NETWORK_ERROR =
  "Le serveur de l'application ne répond pas. Vérifiez que la fenêtre noire " +
  "« Controle Agences » est toujours ouverte, sinon relancez RUN_APP.bat."

async function request(url, options = {}) {
  let response
  try {
    response = await fetch(url, options)
  } catch {
    throw new Error(NETWORK_ERROR)
  }
  if (!response.ok) {
    let message = `Erreur du serveur (${response.status}).`
    try {
      message = (await response.json()).error || message
    } catch {
      /* réponse non JSON : message générique */
    }
    throw new Error(message)
  }
  return response
}

export async function getJson(url) {
  return (await request(url)).json()
}

export async function postJson(url, body) {
  const response = await request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return response.json()
}

export async function postJsonForBlob(url, body) {
  const response = await request(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return response.blob()
}

export async function postForm(url, formData) {
  return (await request(url, { method: 'POST', body: formData })).json()
}
