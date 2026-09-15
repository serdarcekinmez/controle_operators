/**
 * Passerelle Google Sheets / Drive — Application de contrôle agences.
 *
 * À coller dans l'éditeur Apps Script du classeur d'archivage
 * (Extensions > Apps Script), puis à déployer en « Application web » :
 *   - Exécuter en tant que : Moi
 *   - Qui a accès : Tout le monde
 *
 * Propriétés du script (Paramètres du projet > Propriétés du script) :
 *   - SHEETS_TOKEN     (obligatoire) jeton identique à « sheets_token »
 *                      dans config.json. La fonction genererJeton() peut
 *                      en créer un.
 *   - SHEET_NAME       (facultatif) nom de l'onglet, « Controles » par défaut.
 *   - DRIVE_FOLDER_ID  (facultatif) dossier Drive des PDF ; créé
 *                      automatiquement au premier dépôt s'il est absent.
 *
 * Actions :
 *   GET  ?action=ping
 *   GET  ?action=query&branches=A|B&date_from=AAAA-MM-JJ&date_to=AAAA-MM-JJ
 *   POST {action: "append", rows: [...]}      (ajout ou mise à jour par report_id)
 *   POST {action: "upload_pdf", report_id, filename, content_base64}
 */

// Doit rester identique à SHEET_COLUMNS dans constants.py.
var HEADERS = [
  'report_id',
  'horodatage',
  'date_controle',
  'agence',
  'controleur',
  'journee_comptable',
  'caisses',
  'acr',
  'affichage',
  'affichage_obligatoire',
  'nb_problemes',
  'observations',
  'fichier_pdf',
  'lien_drive',
  'email_envoye',
];

var DEFAULT_SHEET_NAME = 'Controles';
var DEFAULT_FOLDER_NAME = 'Rapports contrôle niveau 1';


// --------------------------------------------------------------------------
// Points d'entrée
// --------------------------------------------------------------------------
function doGet(e) {
  return respond_(function () {
    var params = (e && e.parameter) || {};
    checkToken_(params.token);
    switch (params.action) {
      case 'ping':
        return { ok: true, sheet: getSheet_().getName() };
      case 'query':
        return { ok: true, rows: queryRows_(params) };
      default:
        throw new Error('Action inconnue : ' + params.action);
    }
  });
}

function doPost(e) {
  return respond_(function () {
    var body;
    try {
      body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    } catch (err) {
      throw new Error('Requête illisible (JSON attendu).');
    }
    checkToken_(body.token);
    switch (body.action) {
      case 'append':
        return appendRows_(body.rows || []);
      case 'upload_pdf':
        return uploadPdf_(body);
      default:
        throw new Error('Action inconnue : ' + body.action);
    }
  });
}

/** Utilitaire à lancer une fois depuis l'éditeur : crée et affiche le jeton. */
function genererJeton() {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('SHEETS_TOKEN');
  if (!token) {
    token = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, '');
    props.setProperty('SHEETS_TOKEN', token);
  }
  Logger.log('Jeton à copier dans config.json (sheets_token) : ' + token);
}


// --------------------------------------------------------------------------
// Outils
// --------------------------------------------------------------------------
function respond_(fn) {
  var result;
  try {
    result = fn();
  } catch (err) {
    result = { ok: false, error: String((err && err.message) || err) };
  }
  return ContentService.createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

function checkToken_(token) {
  var expected = PropertiesService.getScriptProperties().getProperty('SHEETS_TOKEN');
  if (!expected) {
    throw new Error('Jeton non défini côté Google (propriété SHEETS_TOKEN du script).');
  }
  if (String(token || '') !== expected) {
    throw new Error('Jeton invalide : vérifiez « sheets_token » dans config.json.');
  }
}

function getSheet_() {
  var name = PropertiesService.getScriptProperties().getProperty('SHEET_NAME')
    || DEFAULT_SHEET_NAME;
  var spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
    sheet.setFrozenRows(1);
  }
  return sheet;
}

/** Position (base 0) de chaque colonne ; ajoute en fin de ligne celles qui manquent. */
function headerIndex_(sheet) {
  var width = sheet.getLastColumn();
  var header = sheet.getRange(1, 1, 1, width).getDisplayValues()[0];
  var index = {};
  header.forEach(function (name, i) {
    if (name) index[name] = i;
  });
  HEADERS.forEach(function (name) {
    if (!(name in index)) {
      sheet.getRange(1, width + 1).setValue(name).setFontWeight('bold');
      index[name] = width;
      width++;
    }
  });
  return index;
}

/** Empêche qu'un texte saisi (« =... », « +... ») soit interprété comme formule. */
function asText_(value) {
  var text = value == null ? '' : String(value);
  return /^[=+\-@]/.test(text) ? "'" + text : text;
}


// --------------------------------------------------------------------------
// Actions
// --------------------------------------------------------------------------
function appendRows_(rows) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sheet = getSheet_();
    var index = headerIndex_(sheet);
    var width = sheet.getLastColumn();

    // report_id -> numéro de ligne existant
    var positions = {};
    var lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      sheet.getRange(2, index.report_id + 1, lastRow - 1, 1).getDisplayValues()
        .forEach(function (cell, i) {
          if (cell[0]) positions[cell[0]] = i + 2;
        });
    }

    var added = 0;
    var updated = 0;
    rows.forEach(function (row) {
      var id = String(row.report_id || '');
      if (!id) return;

      var rowNumber = positions[id];
      var values;
      if (rowNumber) {
        values = sheet.getRange(rowNumber, 1, 1, width).getValues()[0];
        updated++;
      } else {
        rowNumber = sheet.getLastRow() + 1;
        values = [];
        for (var c = 0; c < width; c++) values.push('');
        positions[id] = rowNumber;
        added++;
      }

      HEADERS.forEach(function (name) {
        if (name in row) values[index[name]] = asText_(row[name]);
      });

      // Format texte : évite que dates et références soient converties.
      sheet.getRange(rowNumber, 1, 1, width).setNumberFormat('@').setValues([values]);
    });

    return { ok: true, added: added, updated: updated };
  } finally {
    lock.releaseLock();
  }
}

function queryRows_(params) {
  var sheet = getSheet_();
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];

  var index = headerIndex_(sheet);
  var data = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getDisplayValues();
  var branches = params.branches ? String(params.branches).split('|') : [];
  var from = params.date_from || '';
  var to = params.date_to || '';

  var rows = [];
  data.forEach(function (values) {
    var row = {};
    HEADERS.forEach(function (name) {
      row[name] = values[index[name]] || '';
    });
    if (!row.report_id) return;
    if (branches.length && branches.indexOf(row.agence) === -1) return;
    if (from && row.date_controle < from) return;
    if (to && row.date_controle > to) return;
    rows.push(row);
  });

  // Les plus récents d'abord.
  rows.sort(function (a, b) {
    return (b.date_controle + b.horodatage).localeCompare(a.date_controle + a.horodatage);
  });
  return rows;
}

function uploadPdf_(body) {
  if (!body.content_base64) throw new Error('Contenu du PDF manquant.');
  var filename = String(body.filename || ('rapport_' + (body.report_id || 'sans_ref') + '.pdf'));
  var blob = Utilities.newBlob(
    Utilities.base64Decode(body.content_base64), 'application/pdf', filename
  );
  var file = getFolder_().createFile(blob);
  if (body.report_id) file.setDescription('Réf. rapport : ' + body.report_id);
  return { ok: true, url: file.getUrl() };
}

function getFolder_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('DRIVE_FOLDER_ID');
  if (id) return DriveApp.getFolderById(id);

  var folders = DriveApp.getFoldersByName(DEFAULT_FOLDER_NAME);
  var folder = folders.hasNext() ? folders.next() : DriveApp.createFolder(DEFAULT_FOLDER_NAME);
  props.setProperty('DRIVE_FOLDER_ID', folder.getId());
  return folder;
}
