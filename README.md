# Tsintuwa — Système de gestion des objets perdus

Tsintuwa (mot haoussa qui évoque le fait de trouver quelque chose, par hasard ; ici, l'objet que l'on retrouve pour le rendre à son propriétaire) est une plateforme de gestion des objets perdus et trouvés pour les établissements d'enseignement et les compagnies de transport. Projet réalisé dans le cadre d'un
mémoire de fin de cycle Master 2 — Génie Logiciel, Institut Africain de
Technologie (IAT), Niamey, Niger.

## Structure du projet

```
objets_trouves/
├── app/
│   ├── main.py           # Point d'entrée de l'application FastAPI
│   ├── database.py       # Connexion et session à la base de données
│   ├── config.py         # Lecture des variables d'environnement
│   ├── models/           # Tables de la base de données (SQLAlchemy)
│   ├── schemas/          # Formats de données validés en entrée/sortie de l'API (Pydantic)
│   ├── routers/          # Points d'accès de l'API, regroupés par ressource
│   ├── services/         # Logique réutilisable (photos, habillage, couleurs, rapprochement...)
│   ├── migrations/       # Évolutions du schéma de la base (Alembic)
│   ├── scripts/          # Outils en ligne de commande (super-administrateur, habillage de démonstration)
│   ├── assets/demo/      # Logos et photos de démonstration (IAT, Rimbo, STM, Amana, SONITRAV)
│   └── static/           # Pages HTML/CSS/JS (interface agent, écran, portail)
├── tests/                # Tests automatisés
├── requirements.txt      # Dépendances Python du projet
├── .env.example          # Modèle de fichier de configuration
├── Dockerfile            # Image de l'application
└── docker-compose.yml    # Orchestration application + base de données
```

## Démarrage (développement local avec Docker)

1. Copier `.env.example` vers `.env` et adapter les valeurs.
2. Lancer : `docker compose up --build`
3. L'API est accessible sur http://localhost:8000
4. La documentation interactive générée automatiquement par FastAPI est accessible sur http://localhost:8000/docs

## Habillage des organisations (Étape 10)

Chaque organisation a son identité visuelle : identifiant d'adresse (`iat`), logo, photo de fond et
couleurs. Pour appliquer l'habillage de démonstration à IAT, Rimbo, STM, Amana et SONITRAV :

```
docker compose exec api python -m app.scripts.habillage_demo
```

## Portail public (Étape 11)

Chaque organisation a une page publique à son identifiant court : `http://localhost:8000/iat`,
`/rimbo`, `/stm`, `/amana`, `/sonitrav`, `/nizar`, `/ema`, `/salim`. Un usager sans compte y déclare un objet perdu (le système cherche aussitôt
une correspondance) et, si l'organisation a activé la consultation à distance, voit les objets trouvés.
La page est conçue d'abord pour un téléphone et s'habille des couleurs, du logo et de la photo de
l'organisation. Fichiers : `app/static/portail/` ; routes : `app/routers/portail.py`.

## Interface des agents (Étape 12)

Chaque organisation a aussi son espace de travail à `/{identifiant}/agent` (par exemple
`http://localhost:8000/iat/agent`) : connexion, liste des objets, enregistrement d'un objet avec photo,
fiche avec code QR à imprimer, remise à son propriétaire (contrôle du détail secret, pièce d'identité),
déclarations de perte et changement de mot de passe. Les droits d'enregistrement et de restitution
sont vérifiés par le serveur ; la page ne fait que masquer ce que la personne ne peut pas faire.
Fichiers : `app/static/agent/` ; routes ajoutées : `GET /objets/{id}/signalements` et `GET /{identifiant}/agent`.
`GET /objets/` et `GET /objets/{id}` sont désormais réservées au personnel connecté de l'organisation.

## Écran d'affichage du hall (Étape 13)

`http://localhost:8000/iat/affichage` : une page plein écran à mettre sur une télévision à l'accueil.
Elle montre les objets trouvés (6 à la fois ; chaque objet est mis en valeur 5 secondes, soit 30 secondes par page,
puis la page suivante s'il y en a plus), l'heure, et un code QR pour
déclarer une perte depuis son téléphone. Elle se met à jour toute seule toutes les 30 secondes et n'expose que
ce que le portail public expose déjà. Touche F : plein écran. Fichiers : `app/static/affichage/` ;
route ajoutée : `GET /portail/{identifiant}/qrcode`. Une fois le site en ligne, renseigner
`ADRESSE_PUBLIQUE` dans `.env` (voir `.env.example`) pour que le code QR pointe vers la bonne adresse.

## Tableau de bord et historique (Étape 14)

Deux onglets réservés aux administrateurs de l'interface `/{identifiant}/agent` :

- **Tableau de bord** : objets en attente, remis ce mois-ci, déclarations en cours, taux et délai moyen de remise,
  objets bientôt en fin de conservation, graphique des 30 derniers jours, objets en attente par catégorie.
  Le super-administrateur choisit l'organisation et voit une comparaison de toutes les organisations.
- **Historique** : journal des remises (filtres par dates, agent, texte ; export CSV), historique d'une personne
  par numéro de téléphone, et frise de la vie d'un objet sur sa fiche.

Routes ajoutées : `GET /statistiques/`, `GET /statistiques/comparaison`, `GET /historique/remises`,
`GET /historique/agents`, `GET /historique/objets/{id}`, `GET /historique/personnes`.
Les chiffres sont des totaux ; le numéro de pièce d'identité n'est jamais renvoyé en entier.

## Notifications par e-mail (Étape 15)

Sur le portail, l'usager peut donner une adresse e-mail (facultative) avec sa déclaration. Il reçoit alors
un courriel de confirmation, puis un courriel dès qu'un objet pouvant être le sien est enregistré
(catégorie et marche à suivre seulement : jamais de photo ni de détail caché). L'adresse est rattachée
à la déclaration, pas à la personne. Un échec d'envoi n'affecte jamais l'utilisateur : il est seulement
écrit dans les journaux (`docker compose logs api`). Les SMS restent simulés.

- **Essai et démonstration** : `docker compose up -d --build` démarre aussi MailHog, une boîte de réception
  factice. Les courriels y sont lisibles sur `http://localhost:8025` ; rien ne part vers l'extérieur.
- **Production** : renseigner `SMTP_HOST`, `SMTP_PORT`, `SMTP_UTILISATEUR`, `SMTP_MOT_DE_PASSE`, `SMTP_STARTTLS`
  et `COURRIEL_EXPEDITEUR` dans `.env` (voir `.env.example`), et supprimer le service `mailhog` de `docker-compose.yml`.
  `SMTP_HOST` vide = aucun courriel envoyé.

Base de données : migration Alembic `0003` (colonne `email` sur `signalements_perte`), appliquée au démarrage.

## Habillage commun et cloche d'alertes (Étape 15 bis)

Tous les profils (agent, agent de restitution, administrateur, super-administrateur) partagent le même
habillage, aux couleurs de leur organisation : sur ordinateur, un menu latéral à gauche et une barre en haut
(titre de la page, cloche, compte) ; sur téléphone, une barre en haut et la navigation flottante en bas.
Chacun ne voit que les entrées auxquelles il a droit.

La **cloche** affiche les alertes de l'organisation, recalculées à chaque appel (jamais stockées) :
déclarations avec un objet correspondant (tout le personnel) et objets bientôt en fin de conservation
(administrateurs). Le nombre est actualisé chaque minute ; ouvrir la cloche le remet à zéro (mémorisé dans le
navigateur de chaque personne). Route ajoutée : `GET /alertes/`.

Le tableau de bord gagne les tuiles « Trouvés en 30 jours » (avec courbe), « Remis ce mois-ci » (avec courbe),
un anneau pour le taux de remise, la tuile « Objets archivés », et un classement des catégories.

Les évolutions de la base sont gérées par Alembic et appliquées automatiquement au démarrage :
mettre l'application à jour ne fait perdre aucune donnée.

## Retouches et choix de la langue (Étape 15 ter)

- Le menu commence par **« Tableau de bord »** (pour les profils qui y ont droit) ; tous les boutons, y compris
  ceux de l'écran « Déclarations », ont le même habillage aux couleurs de l'organisation.
- **Langues** du portail public et de l'écran du hall : français, anglais, haoussa, zarma et arabe (l'arabe passe
  la page de droite à gauche). Le visiteur choisit sa langue avec le sélecteur en haut de page ; son choix est
  mémorisé dans son navigateur. Sans choix, la langue du téléphone est utilisée (français par défaut).
- **Écran du hall** : français seul par défaut. Pour alterner les langues, ajouter à l'adresse
  `?langues=fr,en,ha,dje,ar` (la langue change quand tous les objets ont défilé dans la langue en cours ; la liste peut être plus courte).
- Les textes sont dans `app/static/i18n/` : un fichier par langue (`fr.js`, `en.js`, `ha.js`, `dje.js`, `ar.js`).
  Corriger une traduction = modifier une ligne de ce fichier. Une clé absente retombe sur le français.
- Le haoussa et le zarma sont des **traductions à faire relire** par des locuteurs avant la mise en service
  (voir le tableau de relecture fourni à part).
- L'interface du personnel (agents, administrateurs) reste en français.
- **Photos** : réduites à 1600 px (navigateur puis serveur) à l'envoi, et affichées ENTIÈRES dans les cartes (hall, portail,
  interface agent), le reste de la carte étant rempli par la même photo agrandie et floutée : ni rognage, ni débordement.
- **Catégories d'objets** : une liste commune (67 catégories, dont tapis de prière, casquette, bonnet, chapelet,
  gourde, carte scolaire, passeport, clé USB, argent, chaussures, permis de conduire, hijab ou voile, carte professionnelle, chaussettes, produits (médicaux, cosmétiques, alimentaires, d'hygiène, ménagers), ustensiles de cuisine, parfums, amplificateur sonore, boissons, papiers de voiture ou moto, kit de maquillage, casque de moto, carte de crédit, batterie, objets électroniques, pièces mécaniques, outils de chantier, carte SIM, coran, clavier, souris, tenue de sport, matériel électrique, kit pour bébé, pièces de téléphone, bazin ou tissu, outils de réparation…) plus des catégories propres au secteur (écoles :
  tenue scolaire, ensemble géométrique, bic, calculatrice, kit de maintenance ou de robotique, reçu de paiement ou quittance, copie de devoir ou d'examen, relevé de notes ou bulletin ; transport : billet de voyage, matériel de plomberie, matériel de soudure) ; « Autre » reste en dernier. Elles sont définies dans
  `app/services/categories.py` et servies par `GET /portail/{slug}/categories`.
- **Matricule de l'étudiant** : champ facultatif à la restitution, affiché seulement dans les organisations du secteur éducation ;
  enregistré avec la remise (colonne `matricule_etudiant`, migration `0005`), visible dans l'historique et l'export CSV.

## Gestion de l'équipe (Étape 17)

- **Onglet « Équipe »** (administrateurs seulement) dans l'interface agent : liste des comptes de l'organisation, ajout d'un agent
  (nom, identifiant, droits d'enregistrement et de restitution, mot de passe provisoire proposé par le bouton « Générer »),
  modification des droits d'un clic, désactivation / réactivation, nouveau mot de passe provisoire.
- Le mot de passe provisoire n'est affiché qu'une seule fois, avec l'identifiant et l'adresse de connexion (bouton « Copier ») ;
  l'agent doit en choisir un à sa première connexion. Chaque action est tracée dans le journal d'audit.
- Aucune nouvelle route : l'interface utilise `POST/GET/PATCH /utilisateurs/…` déjà protégées (un administrateur ne gère que les agents de son organisation).

### Créer d'autres administrateurs (0.15.1)

Un administrateur peut créer des agents **et d'autres administrateurs** dans sa propre organisation (onglet Équipe, champ « Type de compte »), jusqu'à **5 administrateurs** par organisation. Il ne peut pas créer de super-administrateur, ni désactiver ou modifier un autre administrateur : seul le super-administrateur le peut. Chaque création est tracée au journal d'audit.

## Corrections et paramètres (Étape 18)

- **Corriger un objet** (bouton sur la fiche, agents autorisés à enregistrer et administrateurs) : catégorie, date, lieu, détail secret.
  Un objet remis ou archivé n'est plus modifiable. Si la catégorie ou la date change, le rapprochement est refait.
- **Corriger une déclaration** (écran « Déclarations », personnel de l'organisation) : catégorie, description, date, lieu.
  Le citoyen ne peut pas modifier sa déclaration lui-même (il n'a pas de compte) ; il peut en refaire une.
- **Désarchiver un objet** (administrateurs) : l'objet redevient « En attente » et le délai de conservation repart d'aujourd'hui
  (colonne `retention_depuis`, migration `0006`) ; sans cela l'archivage automatique le reprendrait aussitôt.
- **Modifier un compte** (onglet Équipe) : le nom, toujours ; l'identifiant seulement tant que la personne n'a pas choisi son
  mot de passe ni commencé à travailler. Ensuite : désactiver le compte et en créer un autre.
- **Onglet « Paramètres »** (administrateurs) : délai de conservation (1 à 3650 jours) et consultation à distance du portail.
- **Référence du talon** : la référence remise au citoyen (8 caractères) s'affiche sur chaque déclaration de l'écran « Déclarations » et dans la liste de remise ; la barre de recherche de cet écran retrouve une déclaration par référence, nom, téléphone ou catégorie.
- **Apparence** (même onglet) : couleurs (principale, accent, fond, avec retour au calcul par défaut), logo (avec option « rendre transparent le fond blanc ») et photo de fond ; les changements s'appliquent aussi au portail public et à l'écran d'affichage.
- Chaque correction ou changement de paramètres est tracé dans le journal d'audit.
- La migration `0006` renomme aussi, dans les données existantes, « Écouteurs » en « Écouteurs ou baladeur » et
  « Kit de maintenance et robotique » en « Kit de maintenance ou de robotique ».
- Tests : `tests/test_etape18.py`.

## Catégories personnalisées (Étape 19)

L'administrateur d'une organisation ajoute ses propres catégories dans **Paramètres → Catégories personnalisées** : nom (en français), icône choisie dans un catalogue de 84 pictogrammes distincts, traductions facultatives (anglais, haoussa, zarma, arabe ; repli sur le français si vide).

- Maximum 30 par organisation ; un nom déjà utilisé (y compris par une catégorie standard) est refusé ; le nom ne peut plus être changé après création.
- Une catégorie peut être désactivée puis réactivée (les objets existants la conservent).
- Elles apparaissent à l'enregistrement, sur le portail public et à l'affichage du hall, traduites selon la langue.
- La table `categories_personnalisees` est créée au démarrage, sans migration. Actions tracées au journal d'audit.

## Sécurité et finition (Étape 16)

- **Limitation des tentatives** : après 5 échecs de connexion (même adresse et même identifiant) en 5 minutes,
  l'accès est bloqué quelques minutes (erreur 429), même avec le bon mot de passe. Les formulaires publics
  (déclaration de perte) sont limités à 20 requêtes par adresse sur 10 minutes. Réglable dans `.env`.
  Les compteurs sont en mémoire : remis à zéro au redémarrage (limite connue).
- **Sessions** : changer ou réinitialiser un mot de passe, ou désactiver un compte, met fin à TOUTES les sessions
  ouvertes de ce compte (autre téléphone, poste oublié).
- **Mot de passe provisoire** : un compte créé par un administrateur, ou dont le mot de passe est réinitialisé,
  doit choisir son propre mot de passe à la première connexion ; tant que ce n'est pas fait, le serveur refuse
  tout le reste (403).
- **Journal d'audit** (onglet « Journal », administrateurs) : connexions réussies, échouées ou bloquées, changements
  de mot de passe, gestion des comptes, archivages. Lecture seule ; jamais de mot de passe ni de donnée d'usager.
  Route : `GET /audit/`.
- **Archivage automatique** : un objet resté « en attente » au-delà du délai de conservation de son organisation
  est archivé (jamais supprimé), vérifié au démarrage puis toutes les 6 heures. `ARCHIVAGE_AUTO=false` le désactive.
- **Téléphone** : le serveur applique lui-même la règle de la page (8 chiffres du Niger ou numéro étranger en +).
- Migration Alembic `0004` (deux colonnes sur `utilisateurs`) ; la table `journal_audit` est créée au démarrage.
- Tests sans base de données : `python -m unittest discover -s tests -v`.

## Documentation du projet

Chaque étape de développement est accompagnée d'un document expliquant le code écrit,
disponible en parallèle de ce dépôt.
