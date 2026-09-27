# Image de base légère avec Python 3.12
FROM python:3.12-slim

# Dossier de travail à l'intérieur du conteneur
WORKDIR /app

# On copie d'abord uniquement requirements.txt pour profiter du cache Docker :
# tant que ce fichier ne change pas, l'installation des dépendances n'est pas refaite.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# On copie ensuite le code de l'application
COPY ./app ./app

# Commande de démarrage du serveur au lancement du conteneur
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
