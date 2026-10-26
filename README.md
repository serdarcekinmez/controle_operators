# Application de contrôle agences — Contrôle niveau 1 (V4)

Application **locale** (poste de travail Windows) permettant à un contrôleur
de remplir un formulaire de contrôle niveau 1, de générer **un seul PDF
final** (rapport + documents scannés) et de l'ajouter à **son fichier de
contrôle Excel**. L'envoi par e-mail (Outlook) sera ajouté dans une version
future.

> ⚠️ Cette application ne contient **aucune donnée client**. Elle enregistre
> uniquement si les points de contrôle interne ont été vérifiés ou non.
> Elle fonctionne **en local** : le serveur n'écoute que sur ce poste
> (`127.0.0.1`), rien n'est exposé sur le réseau, aucun compte en ligne
> n'est utilisé.

### Nouveautés de la V4

- Nouvelle interface (React), plus claire : **vert** = conforme / réussi,
  **rouge** = anomalie / erreur, **orange** = une action est attendue de
  vous, **bleu** = boutons et informations.
- **Avec Edge ou Chrome : plus besoin de retélécharger le fichier Excel.**
  Vous ouvrez votre fichier une fois ; chaque contrôle y est enregistré
  directement. Au lancement suivant, l'application vous propose de
  **reprendre** ce fichier en un clic.
- Un panneau **« Finaliser le contrôle »** indique en permanence ce qui est
  fait et ce qu'il reste à faire.
- Les champs manquants sont surlignés en rouge, et la page vous y emmène.
- Les documents scannés sont vérifiés **dès leur ajout** (un fichier abîmé
  est signalé tout de suite).
- Bouton **« Commencer un nouveau contrôle »** après chaque rapport.
- Suppression d'un contrôle : on le **choisit dans une liste** au lieu de
  retaper sa date, son heure et son contrôleur.
- Votre nom est retenu d'une fois sur l'autre.

---

## 1. Installer Python (une seule fois)

1. Téléchargez **Python 3.13** (recommandé ; 3.10 à 3.14 fonctionnent) :
   <https://www.python.org/downloads/>
2. Lancez l'installateur.
3. **TRÈS IMPORTANT** : cochez la case **« Add Python to PATH »** sur le
   premier écran, puis cliquez sur « Install Now ».

Node.js n'est **pas** nécessaire : l'interface est déjà prête dans le
dossier `frontend/dist`.

---

## 2. Installer l'application (une seule fois)

> **Étape 0 — Copiez le dossier de l'application sur le disque local du PC**
> (ex. `C:\Users\<votre nom>\ControleAgences` ou le Bureau), **jamais** sur
> un chemin réseau (`\\serveur\...`).

> **Étape 1 — Double-cliquez sur `SETUP.bat`**

Il crée un environnement isolé (`.venv`) et installe les composants (Flask,
Waitress, ReportLab, Pillow, pypdf, openpyxl). Comptez 1 à 2 minutes.

---

## 3. Lancer l'application

> **Étape 2 — Double-cliquez sur `RUN_APP.bat`**

- Le navigateur s'ouvre tout seul sur l'application.
- Sinon, ouvrez votre navigateur à l'adresse **http://127.0.0.1:8600**
- Laissez la fenêtre noire ouverte tant que vous utilisez l'application.
- Pour quitter : bouton **« Quitter l'application »** (en haut à droite).
  L'application demande **« Avez-vous enregistré votre travail ? »** :
  **« Oui, quitter »** ferme l'application (et la fenêtre noire),
  **« Retour à l'application »** annule. Fermer la fenêtre noire fonctionne
  aussi.
- Si l'application est déjà ouverte, `RUN_APP.bat` affiche simplement la
  page existante.

**Navigateur conseillé : Microsoft Edge ou Google Chrome** (enregistrement
direct dans le fichier Excel). Avec Firefox, tout fonctionne aussi, mais il
faut télécharger le fichier Excel après chaque contrôle (voir section 5).

> (Facultatif) **`CREATE_SHORTCUT.bat`** crée une icône « Controle
> Agences » sur le Bureau.

---

## 4. Faire un contrôle

La page « **Nouveau contrôle** » se lit de haut en bas :

1. **Informations générales** : votre nom, l'agence, la date et l'heure
   (par défaut : maintenant ; le bouton 🕘 remet l'heure actuelle).
2. **Points de contrôle** : pour chaque point, **OK** (vert) ou
   **Anomalie** (rouge). En cas d'anomalie, décrivez-la : c'est
   obligatoire. Un second clic sur le même bouton annule le choix.
3. **Observations générales** (facultatif).
4. **Documents scannés** (facultatif) : glissez vos PDF / JPG / PNG dans
   le cadre bleu. Chaque document affiche « Prêt » (vert) ou « illisible »
   (rouge, il sera ignoré). La corbeille retire un document.

À droite, le panneau **« Finaliser le contrôle »** résume l'avancement
(✔ vert = fait, ⚠ orange = à faire, ✖ rouge = problème). Cliquez ensuite
sur **« Créer le rapport PDF »** :

- les images sont converties en pages PDF, tout est réuni en **un seul
  PDF** (page 1 = rapport, puis les documents) ;
- le contrôle est **ajouté automatiquement** à votre fichier Excel ;
- **« Ouvrir le PDF »** / **« Télécharger »** pour le consulter ; une copie
  est conservée dans le dossier `reports` de l'application.

Si vous modifiez le formulaire après coup, le panneau indique **« À
recréer »** (orange) : cliquez sur « Recréer le rapport PDF ».
Puis **« Commencer un nouveau contrôle »** vide le formulaire (votre nom
est conservé).

---

## 5. Le fichier de contrôle Excel

Chaque contrôleur conserve **son propre fichier Excel** (`.xlsx`) sur son
poste. Il ne quitte jamais l'ordinateur.

### Première fois

Dans le bloc **« Mon fichier Excel »**, cliquez sur le bouton orange
**« Première fois ? Créer mon fichier »** (renseignez d'abord votre nom :
votre prénom apparaît dans le nom proposé, ex. `261025 - Jean.xlsx`).
Avec Edge / Chrome, choisissez où l'enregistrer (par exemple
**Documents**) : c'est ce fichier qui sera mis à jour ensuite.

### Avec Edge ou Chrome (recommandé)

1. **« Ouvrir mon fichier Excel »** (ou **« Reprendre « … » »** s'il est
   proposé) — la première fois, le navigateur demande l'autorisation de
   modifier le fichier : acceptez.
2. À chaque contrôle, **« Créer le rapport PDF »** ou **« Enregistrer ce
   contrôle dans Excel »** écrit **directement** dans le fichier. Le
   message vert « Votre fichier … est à jour » le confirme.
3. Rien à télécharger. **« Télécharger une copie »** reste disponible si
   vous voulez une sauvegarde.

> Si le fichier est **ouvert dans Excel** au moment de l'enregistrement,
> un message orange s'affiche : fermez-le dans Excel, puis cliquez sur
> **« Réessayer d'écrire dans le fichier »**.

### Avec un autre navigateur (Firefox…)

1. **« Ouvrir mon fichier Excel »** : choisissez votre dernier fichier
   (en général dans **Téléchargements**).
2. Enregistrez vos contrôles comme ci-dessus.
3. Cliquez sur le bouton orange **« Télécharger le fichier de
   contrôle »** : le fichier à jour (`AAMMJJ - Prénom.xlsx`) arrive dans
   vos Téléchargements. Rouvrez **ce dernier fichier** au contrôle suivant.

Tant que le fichier n'est pas téléchargé, l'application l'indique en
orange et vous prévient si vous fermez la page.

### Contenu du fichier

- Onglet **« Controles »** : tous les contrôles, triés par date puis par
  heure (colonnes Date et Heure séparées).
- **Un onglet par agence** (« Lyon », « Rivoli »...), recréé à chaque
  enregistrement : ne le modifiez pas à la main.
- Un contrôle est identifié par **sa date, son heure et son contrôleur** :
  l'enregistrer une seconde fois met sa ligne à jour (jamais de doublon).
  Deux contrôles du même contrôleur doivent donc avoir des heures
  différentes (l'application le signale).
- Vous pouvez annoter le fichier dans Excel : vos colonnes et onglets sont
  conservés. Ne renommez pas l'onglet « Controles » ni ses en-têtes.
- Les fichiers créés avec la V3 s'utilisent tels quels.

### Supprimer un contrôle

Bloc « Mon fichier Excel » → **« Supprimer un contrôle du fichier »**, puis
au choix :

- **Rechercher** : remplissez un ou plusieurs critères — **date**, **nom du
  contrôleur** (même partiel) et/ou **agence** — puis **« Rechercher »**.
  Cliquez sur **« Supprimer »** à côté du contrôle voulu.
- **Liste déroulante** : choisissez le contrôle dans la liste →
  **« Supprimer ce contrôle »**.

Une confirmation est demandée dans les deux cas.

---

## 6. Consultation des rapports

Onglet **« Consultation des rapports »** :

- votre fichier Excel ouvert est inclus automatiquement ;
- **« Ajouter les fichiers d'autres contrôleurs »** pour une vue
  d'ensemble (seulement lus, jamais modifiés ; un contrôle présent dans
  plusieurs fichiers n'est compté qu'une fois) ;
- choisissez le **périmètre** (une, plusieurs ou toutes les agences) et la
  **période** : les résultats se mettent à jour immédiatement ;
- export **HTML** (impression) ou **Excel** ;
- en bas, les **derniers rapports PDF créés sur ce poste**, à rouvrir en un
  clic.

---

## 7. Envoi par e-mail (bientôt disponible)

Le bouton **« Envoyer par e-mail »** est visible mais **désactivé** : l'envoi
sera branché plus tard sur **Outlook / SharePoint (Microsoft 365)**. Aucun
compte Google n'est utilisé. En attendant, téléchargez le PDF et
transmettez-le par vos moyens habituels.

### (Facultatif) Nom du contrôleur pré-rempli

L'application retient automatiquement le dernier nom saisi. Pour imposer un
nom par défaut sur un poste, créez à côté de `server.py` un fichier
`config.json` (modèle : `config.example.json`) :

```json
{
  "default_controller_name": "Prénom Nom"
}
```

---

## 8. Où sont enregistrés les fichiers

```
reports/AAAA-MM/Agence/   PDF finaux (rapport_final_controle_n1_....pdf)
uploads/AAAA-MM/Agence/   documents scannés d'origine
logs/app.log              journal technique (erreurs...)
data/controles.db         historique local (SQLite)
```

---

## 9. Dépannage

| Problème | Solution |
| --- | --- |
| « Python est introuvable » | Installez Python 3.13 en cochant **« Add Python to PATH »**, puis relancez `SETUP.bat`. |
| L'application ne démarre pas | Relancez `SETUP.bat`, puis `RUN_APP.bat`. Détail dans `logs/app.log`. |
| Le navigateur ne s'ouvre pas tout seul | Ouvrez **http://127.0.0.1:8600**. Laissez la fenêtre noire ouverte. |
| « Le serveur de l'application ne répond pas » | La fenêtre noire a été fermée : relancez `RUN_APP.bat`, puis rechargez la page. |
| « UNC paths are not supported » | Copiez le dossier de l'application sur le disque local (ex. `C:\Controle_Agences`) et relancez `SETUP.bat`. |
| Message orange « n'a pas pu être écrit dans … » | Le fichier est ouvert dans Excel : fermez-le, puis « Réessayer d'écrire dans le fichier ». |
| « Impossible de lire votre fichier … » | Le fichier a été déplacé, renommé ou supprimé : rouvrez-le avec « Ouvrir mon fichier Excel ». |
| Pas de bouton « Reprendre » | Normal avec Firefox, ou si vous utilisez une autre adresse que http://127.0.0.1:8600. Ouvrez votre fichier. |
| « Ce fichier n'a pas pu être ouvert » | Le fichier doit être un classeur `.xlsx` non protégé par mot de passe. Fermez-le dans Excel, puis rouvrez-le. |
| « Ce fichier ne contient pas d'onglet Controles » | Ouvrez le fichier de contrôle créé par l'application. L'onglet « Controles » ne doit pas être renommé. |
| « Le fichier Excel contient déjà un contrôle de … à … » | Un autre contrôle a la même date, la même heure et le même contrôleur : corrigez l'heure. |
| Un document est marqué « illisible » | Le fichier est abîmé ou n'est pas un vrai PDF/JPG/PNG : il ne sera pas joint. Rescannez-le. |
| Le bouton « Envoyer par e-mail » est grisé | Normal : l'envoi Outlook arrive dans une version future. |

---

## 10. Sécurité et confidentialité

- Le serveur n'écoute que sur `127.0.0.1` : il n'est pas joignable depuis
  le réseau.
- Aucun identifiant dans le code, aucun compte en ligne ; `config.json`
  (facultatif) ne contient aucun mot de passe et n'est jamais versionné.
- Seuls les formats PDF / JPG / JPEG / PNG sont acceptés ; les noms de
  fichiers sont nettoyés. Les PDF ne sont servis que depuis le dossier
  `reports` de l'application.
- Le fichier Excel est traité en mémoire et réécrit uniquement à
  l'emplacement que vous avez choisi.

---

## 11. Pour les développeurs

Architecture :

- **Serveur** : `server.py` (Flask + Waitress, Python pur) — API JSON locale
  et service de l'interface construite. Il ne garde aucun état : le
  navigateur renvoie à chaque appel le fichier chargé, les contrôles de la
  séance et les suppressions, et le classeur est recalculé par
  `services/excel_service.py`.
- **Interface** : `frontend/` (React 19 + CSS, construit avec Vite).
  L'accès direct au fichier Excel utilise la *File System Access API*
  (`frontend/src/excelFile.js`) ; sans elle, l'application revient au
  chargement / téléchargement.

Modifier l'interface (Node.js 20.19+ ou 22.12+) :

```bash
cd frontend
npm install
# Développement : serveur Python + Vite avec rechargement à chaud
#   (terminal 1)  ..\.venv\Scripts\python server.py --no-browser
#   (terminal 2)  npm run dev      -> http://localhost:5173
npm run build    # régénère frontend/dist
```

**Pensez à reconstruire et à versionner `frontend/dist`** : c'est ce dossier
que les postes utilisateurs exécutent (ils n'ont pas Node.js).

Évolution possible : empaqueter l'application en `.exe` autonome
(PyInstaller) pour ne plus dépendre de Python installé sur le poste.

### Structure du projet

```
controle_operators/
├── server.py               # Serveur local : API + interface (Flask/Waitress)
├── constants.py            # Agences, items de contrôle, chemins, constantes
├── requirements.txt
├── SETUP.bat / RUN_APP.bat / CREATE_SHORTCUT.bat
├── config.example.json     # Modèle de config.json (facultatif)
├── services/               # Logique métier (reprise de la V3)
│   ├── excel_service.py    # Fichier de contrôle Excel
│   ├── pdf_service.py      # Génération PDF, conversion image, fusion
│   ├── db_service.py       # Historique local SQLite
│   ├── file_service.py     # Dossiers, noms de fichiers, sauvegardes
│   ├── email_service.py    # Objet / corps de l'e-mail (Outlook à venir)
│   ├── config_service.py   # Lecture de config.json
│   └── logging_service.py  # Journalisation
└── frontend/
    ├── src/                # Interface React (App.jsx, components/, styles.css)
    ├── public/             # Logo
    └── dist/               # Interface construite (versionnée)
```
