#!/bin/bash

# Affiche un message pour l'utilisateur
echo "Lancement du worker pour la source 'spotify'..."

# --- Ta commande ---
MONGO_HOSTNAME=localhost MONGO_PORT=27017 python worker.py \
  --task-id "demo-live-matteo" \
  --source-name "spotify" \
  --use-stdin < raw_data/spotify_tc.txt