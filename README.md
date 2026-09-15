# Application de contrôle agences — Contrôle niveau 1

Application **locale** (poste de travail Windows) permettant à un contrôleur
de remplir un formulaire de contrôle niveau 1, de générer **un seul PDF
final** (rapport + documents scannés) et de l'envoyer par email à une boîte
Gmail partagée qui sert d'archive centrale.

> ⚠️ Cette application ne contient **aucune donnée client**. Elle enregistre
> uniquement si les points de contrôle interne ont été vérifiés ou non.
> Elle fonctionne **en local** : pas de serveur web, pas d'exposition à
> internet. La liaison **Google Sheets / Drive** est **facultative** (voir
> section 9) : sans elle, l'application produit le PDF et l'envoie par e-mail
> exactement comme avant.

---

## 1. Ce que fait l'application

1. Vous ouvrez l'application en local (dans votre navigateur).
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
9. Vous téléchargez/ouvrez le PDF, puis cliquez sur **« Envoyer le rapport »**.
10. Le PDF final est envoyé à la boîte Gmail partagée, une copie locale est
    conservée et l'envoi est journalisé.

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
- installe automatiquement les dépendances (Streamlit, ReportLab, Pillow, pypdf) ;
- affiche des messages clairs et reste ouvert à la fin pour que vous puissiez
  lire d'éventuelles erreurs.

L'opération peut prendre 1 à 2 minutes la première fois.

---

## 4. Configurer l'envoi des emails (`config.json`)

L'application a besoin d'un fichier `config.json` (jamais partagé, jamais versionné).

1. Copiez le fichier `config.example.json` et renommez la copie en `config.json`.
2. Ouvrez `config.json` avec le Bloc-notes et renseignez :

```json
{
  "smtp_email": "controle.agences@gmail.com",
  "smtp_app_password": "xxxx xxxx xxxx xxxx",
  "recipient_email": "controle.agences@gmail.com",
  "default_controller_name": "",
  "default_language": "fr"
}
```

- `smtp_email` : l'adresse Gmail partagée qui **envoie** les rapports.
- `smtp_app_password` : un **mot de passe d'application** Gmail (voir ci-dessous).
- `recipient_email` : l'adresse Gmail partagée qui **reçoit** (souvent la même).
- `default_controller_name` : nom pré-rempli au démarrage (facultatif).

> ❌ N'utilisez **jamais** le mot de passe principal du compte Gmail.
> ✅ Utilisez un mot de passe d'application dédié.

---

## 5. Créer un « mot de passe d'application » Gmail

Principe général (l'interface Google peut évoluer) :

1. Le compte Gmail doit avoir la **validation en deux étapes** activée.
2. Allez dans la gestion du compte Google → **Sécurité**.
3. Recherchez **« Mots de passe des applications »**.
4. Générez un nouveau mot de passe d'application (16 caractères, par groupes
   de 4, par ex. `abcd efgh ijkl mnop`).
5. Copiez-le dans `config.json`, champ `smtp_app_password`.

Ce mot de passe ne sert qu'à cette application et peut être révoqué à tout
moment depuis le compte Google.

---

## 6. Lancer l'application

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

## 7. Générer un rapport

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

## 8. Envoyer un rapport

1. Après génération, cliquez sur **« Envoyer le rapport »**.
2. Un message vous indique le succès ou l'échec de l'envoi.
3. Le PDF final (et lui seul) est joint à l'email. Les images d'origine ne
   sont pas jointes séparément.

L'objet de l'email suit le format :
`[Contrôle N1] {agence} - {date} - {contrôleur}`

---

## 9. (Facultatif) Tableau Google Sheets et Drive

Cette partie est **optionnelle**. Si vous avez seulement besoin du rapport
PDF (et de l'e-mail), ignorez-la : l'application fonctionne en **mode local**
et les blocs Google n'apparaissent pas.

### Avec ou sans compte Google

- **Sans liaison configurée** : mode local automatique (PDF + e-mail).
- **Avec liaison configurée** : un interrupteur **« Utiliser Google Sheets /
  Drive »** apparaît dans la barre latérale. Désactivez-le pour travailler
  sans Google ; les contrôles restent enregistrés sur le poste et pourront
  être envoyés au tableau plus tard en le réactivant.
- Dans `config.json`, `"use_google": false` désactive l'interrupteur par
  défaut au démarrage.

Une fois activé, vous disposez de :

- **« Mettre à jour le tableau »** : envoie vers la feuille tous les contrôles
  pas encore synchronisés (un contrôle renvoyé met sa ligne à jour, sans
  doublon) ;
- **« Ajouter le rapport PDF au Drive »** : dépose le PDF final dans un dossier
  du Drive ;
- **« Consultation des rapports »** : recherche par agence et par période,
  export HTML ou CSV (Excel).

### Mise en place (une seule fois, avec le compte Google d'archivage)

1. Créez un classeur Google Sheets (ex. « Contrôles niveau 1 »).
2. Menu **Extensions → Apps Script**. Remplacez le contenu par celui du
   fichier `apps_script/Code.gs`, puis enregistrez.
3. Dans l'éditeur, sélectionnez la fonction **`genererJeton`** et cliquez sur
   **Exécuter** (autorisez l'accès demandé). Le jeton s'affiche dans le
   journal d'exécution : copiez-le.
4. **Déployer → Nouveau déploiement → Application web** :
   - Exécuter en tant que : **Moi** ;
   - Qui a accès : **Tout le monde**.
   Copiez l'URL obtenue (elle se termine par `/exec`).
5. Complétez `config.json` :

```json
{
  "use_google": true,
  "sheets_webapp_url": "https://script.google.com/macros/s/.../exec",
  "sheets_token": "le jeton copié à l'étape 3"
}
```

6. Relancez l'application.

L'onglet « Controles » et le dossier Drive « Rapports contrôle niveau 1 »
sont créés automatiquement au premier envoi. Seules les personnes qui ont le
jeton peuvent lire ou écrire via la passerelle : ne le partagez pas.

> Si vous modifiez `Code.gs`, pensez à **Déployer → Gérer les déploiements →
> Modifier → Nouvelle version**, sinon l'ancienne version reste active.

---

## 10. Où sont enregistrés les fichiers

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

## 11. Dépannage

| Problème | Solution |
| --- | --- |
| « Python n'est pas installé » | Réinstallez Python en cochant **« Add Python to PATH »**. |
| Bandeau « config.json introuvable » | Copiez `config.example.json` en `config.json` et remplissez-le. |
| « Authentification Gmail refusée » | Vérifiez l'adresse et utilisez bien un **mot de passe d'application** (pas le mot de passe principal). |
| « Connexion au serveur Gmail impossible » | Vérifiez votre connexion internet / pare-feu d'entreprise. |
| Une image ne s'ajoute pas au PDF | Le fichier est peut-être corrompu ; un message le signale et le détail est dans `logs/app.log`. |
| L'application ne démarre pas | Lancez d'abord `SETUP.bat`, puis consultez `logs/app.log`. |
| Le navigateur ne s'ouvre pas tout seul | Ouvrez votre navigateur et allez sur **http://localhost:8501**. Laissez la fenêtre noire ouverte. |
| « le port 8501 est déjà utilisé » | L'application est probablement déjà ouverte. Allez simplement sur **http://localhost:8501**, ou fermez l'ancienne fenêtre noire avant de relancer. |
| « UNC paths are not supported » au lancement | Le dossier de l'application doit se trouver sur un disque **local Windows** (ex. `C:\Controle_Agences` ou le Bureau), et non sur un chemin réseau / `\\wsl...`. Copiez le dossier localement puis relancez `SETUP.bat`. |
| « Streamlit n'est pas installé » | Relancez `SETUP.bat` (l'installation des dépendances a probablement échoué). |
| Les blocs Google n'apparaissent pas | Normal en mode local. Renseignez `sheets_webapp_url` et `sheets_token` dans `config.json` et activez l'interrupteur dans la barre latérale. |
| « Jeton invalide » | `sheets_token` dans `config.json` doit être identique à la propriété `SHEETS_TOKEN` du script. |
| « Réponse inattendue » de la passerelle | Le déploiement doit être accessible à **Tout le monde** et l'URL se terminer par `/exec`. |
| « Connexion à Google impossible » | Vérifiez internet / pare-feu ; les contrôles restent en attente et repartiront au prochain clic. |

Pour toute erreur, le détail technique est consigné dans **`logs/app.log`**.

---

## 12. Sécurité et confidentialité

- Aucun identifiant n'est écrit en dur dans le code.
- `config.json` n'est jamais versionné (présent dans `.gitignore`).
- Seuls les formats PDF / JPG / JPEG / PNG sont acceptés ; les noms de
  fichiers sont nettoyés.
- L'application reste **locale** : pas de serveur web public. Seule la
  liaison Google (facultative) échange des données avec le compte
  d'archivage, protégée par un jeton.

---

## 13. Évolutions possibles

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
├── config.example.json     # Modèle de configuration (à copier en config.json)
├── .gitignore
├── SETUP.bat               # Installation (une seule fois)
├── RUN_APP.bat             # Lancement de l'application
├── CREATE_SHORTCUT.bat     # Crée une icône sur le Bureau (facultatif)
├── .streamlit/
│   └── config.toml         # Réglages locaux de Streamlit
├── apps_script/
│   └── Code.gs             # Passerelle Google Sheets / Drive (facultatif)
├── services/
│   ├── __init__.py
│   ├── config_service.py   # Lecture/validation de config.json
│   ├── sheets_service.py   # Synchronisation Google Sheets / Drive
│   ├── pdf_service.py      # Génération PDF, conversion image, fusion
│   ├── email_service.py    # Envoi Gmail SMTP (SSL)
│   ├── file_service.py     # Dossiers, nettoyage de noms, sauvegardes
│   ├── db_service.py       # Historique local SQLite
│   └── logging_service.py  # Journalisation
├── data/                   # Base SQLite (créé automatiquement)
├── reports/                # PDF finaux (créé automatiquement)
├── uploads/                # Documents d'origine (créé automatiquement)
└── logs/                   # Journaux (créé automatiquement)
```
