# Image de base légère avec Python 3.12
FROM python:3.12-slim

# Dossier de travail à l'intérieur du conteneur
WORKDIR /app

# On copie d'abord uniquement requirements.txt pour profiter du cache Docker :
# tant que ce fichier ne change pas, l'installation des dépendances n'est pas refaite.
COPY requirements.txt .

# Installation des dépendances, adaptée à une connexion internet lente ou instable :
#  - --mount=type=cache conserve les paquets déjà téléchargés entre deux tentatives
#    de construction : si la connexion coupe, la tentative suivante repart de là
#    où la précédente s'était arrêtée, au lieu de tout retélécharger ;
#  - --default-timeout et --retries laissent à pip plus de temps et plus
#    d'essais avant d'abandonner un téléchargement.
#  - la boucle ci-dessous relance automatiquement l'installation (jusqu'à 8 fois)
#    si elle échoue, ce qui évite d'avoir à relancer la construction à la main.
RUN --mount=type=cache,target=/root/.cache/pip \
    for i in 1 2 3 4 5 6 7 8; do \
        pip install --default-timeout=120 --retries 10 -r requirements.txt && exit 0; \
        echo "Tentative $i echouee, nouvel essai dans 10 secondes..."; \
        sleep 10; \
    done; \
    exit 1

# On copie ensuite le code de l'application
COPY ./app ./app
COPY ./tests ./tests
COPY alembic.ini .

# Commande de démarrage du serveur au lancement du conteneur
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
