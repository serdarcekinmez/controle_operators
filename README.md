# Application de contrôle agences — Contrôle niveau 1

Application **locale** (poste de travail Windows) permettant à un contrôleur
de remplir un formulaire de contrôle niveau 1, de générer **un seul PDF
final** (rapport + documents scannés), de l'ajouter à **son fichier de
contrôle Excel**. L'envoi par e-mail (Outlook) sera ajouté dans une version
future.

> ⚠️ Cette application ne contient **aucune donnée client**. Elle enregistre
> uniquement si les points de contrôle interne ont été vérifiés ou non.
> Elle fonctionne **en local** : pas de serveur web, pas d'exposition à
> internet. Le suivi des contrôles se fait dans un **fichier Excel local**
> que chaque contrôleur charge puis retélécharge (voir section 7) : aucun
> compte Google n'est nécessaire.

---

## 1. Ce que fait l'application

1. Vous ouvrez l'application en local (dans votre navigateur) et chargez
   votre fichier de contrôle Excel (section 7).
2. Vous saisissez le nom du contrôleur.
3. Vous choisissez l'agence dans une liste déroulante.
4. Vous confirmez la date du contrôle (par défaut : aujourd'hui).
5. Pour chacun des cinq points de « Contrôle niveau 1 », vous choisissez un
   statut **OK** (vert) ou **Problème** (rouge). En cas de problème, un
   commentaire est obligatoire.
6. Vous pouvez écrire des observations (facultatif).
7. Vous pouvez téléverser des documents scannés (PDF / JPG / JPEG / PNG).
8. Vous cliquez sur **« Créer le rapport PDF »**.
   - Les images (JPG/JPEG/PNG) sont **automatiquement converties** en pages PDF.
   - Les PDF déjà fournis sont conservés tels quels.
   - Tout est fusionné en **un seul PDF final** :
     page 1 = rapport, pages suivantes = documents joints.
   - Le contrôle est **ajouté automatiquement** à votre fichier Excel.
9. Vous téléchargez/ouvrez le PDF ; une copie locale est conservée.
10. Vous téléchargez votre **fichier de contrôle Excel** mis à jour.

---

## 2. Installer Python (si ce n'est pas déjà fait)

1. Téléchargez Python 3.10 ou plus récent : <https://www.python.org/downloads/>
2. Lancez l'installateur.
3. **TRÈS IMPORTANT** : cochez la case **« Add Python to PATH »** sur le
   premier écran de l'installateur, puis cliquez sur « Install Now ».

Pour vérifier : ouvrez l'application après l'installation ; si une erreur
« Python n'est pas installé » apparaît, recommencez en cochant bien la case.

---

## 3. Installation de l'application (une seule fois)

> **Étape 0 — Copiez le dossier de l'application sur le disque local du PC**
>
> Le dossier complet doit se trouver sur un disque **local Windows**
> (ex. `C:\Users\<votre nom>\ControleAgences` ou le Bureau), **jamais**
> sur un chemin réseau (`\\serveur\...`) ni un chemin WSL (`\\wsl...`).
> Sinon l'installation échoue et l'application serait très lente.

> **Étape 1 — Double-cliquez sur `SETUP.bat`**

Ce fichier :

- crée un environnement isolé (`.venv`) ;
- installe automatiquement les dépendances (Streamlit, ReportLab, Pillow, pypdf, openpyxl) ;
- affiche des messages clairs et reste ouvert à la fin pour que vous puissiez
  lire d'éventuelles erreurs.

L'opération peut prendre 1 à 2 minutes la première fois.

---

## 4. Envoi par e-mail (bientôt disponible)

Le bouton **« 📧 Envoyer le rapport »** est déjà visible dans le bloc
« Actions du rapport », mais il est **désactivé** pour le moment.

L'envoi sera branché plus tard sur **Outlook / SharePoint (Microsoft 365)**,
avec les comptes des agences et des directions : aucun compte Google ni
Gmail n'est utilisé par l'application. En attendant, téléchargez le PDF avec
**⬇️ Télécharger le rapport** et transmettez-le par vos moyens habituels.

L'objet prévu pour l'e-mail suit le format :
`[Contrôle N1] {agence} - {date} - {contrôleur}` ; le PDF final (et lui
seul) sera joint.

### (Facultatif) Nom du contrôleur pré-rempli

Pour ne pas retaper son nom à chaque contrôle, créez à côté de `app.py` un
fichier `config.json` (modèle : `config.example.json`) :

```json
{
  "default_controller_name": "Prénom Nom"
}
```

---

## 5. Lancer l'application

> **Étape 2 — Double-cliquez sur `RUN_APP.bat`**

- L'application est lancée via l'environnement local (`.venv`), sans dépendre
  d'une commande `streamlit` globale.
- **Patientez quelques secondes** : le navigateur s'ouvre automatiquement sur
  l'application.
- **Si le navigateur ne s'ouvre pas automatiquement**, ouvrez-le manuellement
  et allez à l'adresse :

  **http://localhost:8501**

- **Aucune commande à taper.**
- Laissez la fenêtre noire ouverte tant que vous utilisez l'application.
- Pour quitter : fermez la fenêtre noire.

### (Facultatif) Créer une icône sur le Bureau

> **Étape 3 — Double-cliquez sur `CREATE_SHORTCUT.bat`**

Cela crée une icône **« Controle Agences »** sur votre Bureau. Ensuite, un
simple double-clic sur cette icône lancera l'application.

---

## 6. Générer un rapport

1. Renseignez le **nom du contrôleur** (obligatoire).
2. Choisissez l'**agence** (obligatoire).
3. Vérifiez la **date du contrôle** (par défaut : aujourd'hui).
4. Pour chaque point de **Contrôle niveau 1**, cliquez sur **OK** (vert) ou
   **Problème** (rouge). Si vous choisissez « Problème », un champ de
   commentaire apparaît juste en dessous : il est **obligatoire**.
5. Saisissez d'éventuelles **observations**.
6. (Facultatif) Téléversez des **documents scannés**.
7. Cliquez sur **« Créer le rapport PDF »**.
8. Téléchargez/ouvrez le PDF avec le bouton dédié pour vérifier le contenu.

Vous pouvez générer un rapport **même sans aucun document téléversé**.

---

## 7. Le fichier de contrôle Excel

Chaque contrôleur conserve **son propre fichier Excel** (`.xlsx`) sur son
poste. L'application n'utilise **aucun compte en ligne** (ni Google, ni
autre) : le fichier ne quitte jamais votre ordinateur.

### À chaque contrôle

1. Dans le bloc **« Fichier de contrôle Excel »**, champ **« Mettre à jour
   votre fichier de contrôle »** : choisissez votre fichier (en général dans
   le dossier **Téléchargements**).
2. Remplissez le contrôle et cliquez sur **« Créer le rapport PDF »** :
   le contrôle est **ajouté automatiquement** au fichier, qui est trié par
   date de contrôle.
3. Cliquez sur **« ⬇️ Télécharger le fichier de contrôle »** : le fichier mis
   à jour est enregistré dans vos Téléchargements.
4. Au contrôle suivant, chargez **ce dernier fichier** (le plus récent).

Le fichier téléchargé est nommé **« Agence - AAMMJJ - Prénom.xlsx »**, par
exemple `Lyon - 261016 - Jean.xlsx` (agence du contrôle, date du jour,
prénom du contrôleur) : le plus récent est toujours facile à retrouver.
Vous pouvez supprimer les anciennes versions.

> **Première utilisation** : cliquez sur le bouton rouge **« 🆕 Première
> fois ? Créez votre 1er fichier Excel en cliquant ici »**, en haut à droite
> de la page (renseignez d'abord votre nom : votre prénom apparaît dans le
> nom du fichier). Un fichier Excel vide est prêt ; vos rapports y sont
> ajoutés. Téléchargez-le et gardez-le pour la suite. Le bouton disparaît dès
> qu'un fichier est chargé ou créé.

La page est organisée ainsi : en bas à gauche, **« Actions du rapport »**
(tout ce qui concerne le PDF) ; en bas à droite, **« Fichier de contrôle
Excel »** (chargement et téléchargement du fichier). Tant qu'aucun fichier
n'est chargé, ce bloc affiche un rappel des deux possibilités.

> ⚠️ Si vous oubliez de charger votre fichier, le fichier téléchargé ne
> contient que les contrôles du jour (un avertissement l'indique). Chargez
> votre fichier habituel, même après avoir créé le rapport : le contrôle y
> est ajouté, puis téléchargez à nouveau.

Bon à savoir :

- Plusieurs rapports créés dans la même séance sont tous ajoutés.
- Un contrôle déjà présent (même « Réf. ») est **mis à jour**, jamais
  dupliqué. La colonne « E-mail » restera à « Non » tant que l'envoi
  Outlook n'est pas disponible.
- Vous pouvez ouvrir et annoter le fichier dans Excel : les colonnes et les
  onglets que vous ajoutez sont conservés. Ne renommez pas l'onglet
  **« Controles »** ni ses en-têtes.
- Téléchargez le fichier **avant de fermer l'application** : sinon il faudra
  le recharger et recréer le rapport. Les PDF restent de toute façon
  enregistrés sur le poste (dossier `reports`).

### Consultation des rapports

En bas de page, le bloc **« Consultation des rapports »** recherche dans les
fichiers de contrôle par agence et par période :

- votre fichier (celui du bloc « Fichier de contrôle Excel ») est inclus
  automatiquement ;
- pour une vue d'ensemble, ajoutez les fichiers d'autres contrôleurs dans
  **« Autres fichiers de contrôle à consulter »** (ils sont seulement lus,
  jamais modifiés ; un contrôle présent dans plusieurs fichiers n'est compté
  qu'une fois) ;
- le résultat s'exporte en **HTML** (impression) ou en **Excel**.

---

## 8. Où sont enregistrés les fichiers

```
reports/
  2026-06/
    Lyon/
      rapport_final_controle_n1_lyon_2026-06-09_prenom_nom.pdf

uploads/
  2026-06/
    Lyon/
      (documents scannés d'origine)

logs/
  app.log         (journal technique : erreurs, envois, ...)

data/
  controles.db    (historique local SQLite)
```

L'historique des derniers rapports est aussi visible dans la barre latérale
de l'application (**« Historique local »**).

---

## 9. Dépannage

| Problème | Solution |
| --- | --- |
| « Python n'est pas installé » | Réinstallez Python en cochant **« Add Python to PATH »**. |
| Le bouton « Envoyer le rapport » est grisé | Normal : l'envoi Outlook sera disponible dans une version future. Téléchargez le PDF. |
| Une image ne s'ajoute pas au PDF | Le fichier est peut-être corrompu ; un message le signale et le détail est dans `logs/app.log`. |
| L'application ne démarre pas | Lancez d'abord `SETUP.bat`, puis consultez `logs/app.log`. |
| Le navigateur ne s'ouvre pas tout seul | Ouvrez votre navigateur et allez sur **http://localhost:8501**. Laissez la fenêtre noire ouverte. |
| « le port 8501 est déjà utilisé » | L'application est probablement déjà ouverte. Allez simplement sur **http://localhost:8501**, ou fermez l'ancienne fenêtre noire avant de relancer. |
| « UNC paths are not supported » au lancement | Le dossier de l'application doit se trouver sur un disque **local Windows** (ex. `C:\Controle_Agences` ou le Bureau), et non sur un chemin réseau / `\\wsl...`. Copiez le dossier localement puis relancez `SETUP.bat`. |
| « Streamlit n'est pas installé » | Relancez `SETUP.bat` (l'installation des dépendances a probablement échoué). |
| « Ce fichier n'a pas pu être ouvert » | Le fichier doit être un classeur Excel `.xlsx` non protégé par mot de passe. Fermez-le dans Excel, puis rechargez-le. |
| « Ce fichier ne contient pas d'onglet Controles » | Chargez le fichier de contrôle téléchargé depuis l'application (ou retirez-le et utilisez le bouton rouge en haut à droite de la page). L'onglet « Controles » ne doit pas être renommé. |
| Le contrôle du jour n'est pas dans mon fichier | Le fichier a été téléchargé avant « Créer le rapport PDF », ou sans avoir chargé votre fichier. Chargez votre fichier, puis téléchargez-le à nouveau. |
| Windows ajoute « (1) » au nom du fichier téléchargé | Normal si un fichier du même nom existe déjà. Chargez le plus récent (date AAMMJJ la plus grande) : le nom est recalculé à chaque téléchargement. |

Pour toute erreur, le détail technique est consigné dans **`logs/app.log`**.

---

## 10. Sécurité et confidentialité

- Aucun identifiant n'est écrit en dur dans le code.
- Aucun compte en ligne (Google ou autre) n'est utilisé ; `config.json`
  (facultatif) ne contient aucun mot de passe et n'est jamais versionné.
- Seuls les formats PDF / JPG / JPEG / PNG sont acceptés ; les noms de
  fichiers sont nettoyés.
- L'application reste **locale** : pas de serveur web public, aucun compte
  en ligne pour le suivi. Le fichier de contrôle Excel est traité en
  mémoire et ne quitte jamais le poste.

---

## 11. Évolutions possibles

- Envoi du rapport par **Outlook / SharePoint** (comptes Microsoft 365 des
  agences et des directions), pour les responsables d'agence qui réaliseront
  aussi leurs contrôles dans l'application.
- Cette version (MVP) utilise des lanceurs `.bat`. Une version future pourra
  être empaquetée en exécutable `.exe` autonome avec **PyInstaller** afin de
  ne plus dépendre de Python installé sur le poste.

---

## Structure du projet

```
controle_operators/
├── app.py                  # Application Streamlit (UI + orchestration)
├── constants.py            # Agences, items de contrôle, chemins, constantes
├── requirements.txt
├── README.md
├── config.example.json     # Modèle de config.json (facultatif)
├── .gitignore
├── SETUP.bat               # Installation (une seule fois)
├── RUN_APP.bat             # Lancement de l'application
├── CREATE_SHORTCUT.bat     # Crée une icône sur le Bureau (facultatif)
├── .streamlit/
│   └── config.toml         # Réglages locaux de Streamlit
├── services/
│   ├── __init__.py
│   ├── config_service.py   # Lecture de config.json (facultatif)
│   ├── excel_service.py    # Fichier de contrôle Excel (lecture / mise à jour)
│   ├── pdf_service.py      # Génération PDF, conversion image, fusion
│   ├── email_service.py    # Objet / corps de l'e-mail (envoi Outlook à venir)
│   ├── file_service.py     # Dossiers, nettoyage de noms, sauvegardes
│   ├── db_service.py       # Historique local SQLite
│   └── logging_service.py  # Journalisation
├── data/                   # Base SQLite (créé automatiquement)
├── reports/                # PDF finaux (créé automatiquement)
├── uploads/                # Documents d'origine (créé automatiquement)
└── logs/                   # Journaux (créé automatiquement)
```
