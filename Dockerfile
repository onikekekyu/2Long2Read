# Étape 1: Utiliser une image Python officielle et légère
FROM python:3.11-slim

# Étape 2: Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Étape 3: Copier le fichier des dépendances
COPY requirements.txt .

# Étape 4: Installer les dépendances avec uv en mode --system
RUN pip install uv && uv pip install --no-cache-dir --system -r requirements.txt

# Étape 5: Copier le code source de l'application
COPY ./main.py .
COPY ./ai_analyzer.py . 
COPY ./config ./config

# Étape 6: Exposer le port que l'API utilise
EXPOSE 8000

# Étape 7: Commande pour lancer l'API au démarrage du conteneur
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]