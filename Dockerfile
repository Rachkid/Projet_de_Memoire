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
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=120 --retries 10 -r requirements.txt

# On copie ensuite le code de l'application
COPY ./app ./app

# Commande de démarrage du serveur au lancement du conteneur
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
