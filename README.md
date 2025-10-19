# 🚀 2Long2Read - Analyseur de CGU avec Claude AI

**Système d'analyse automatique de Terms & Conditions utilisant Claude AI, MongoDB, Prometheus et Grafana sur Kubernetes.**

---

## 📋 Prérequis

Avant de commencer, assure-toi d'avoir :

- **Docker Desktop** installé et en cours d'exécution
- **kubectl** installé (inclus avec Docker Desktop)
- **Helm** installé (gestionnaire de packages Kubernetes)
- **Python 3.11+** avec pip
- **Une clé API Anthropic** (Claude AI)

### Vérification rapide

```bash
docker --version
kubectl version --client
helm version
python3 --version
```

---

## 🛠️ Installation Complète (Étape par Étape)

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd theprojectthathelpsyoubetterunderstndhowyourdataisusedineverycompanystermsandconditionsbecausenooneverreadsthem
```

### 2. Configurer l'environnement Python

```bash
# Créer un environnement virtuel
python3 -m venv .venv

# Activer l'environnement
source .venv/bin/activate  # macOS/Linux
# ou
.venv\Scripts\activate     # Windows

# Installer les dépendances
pip install -r requirements.txt
```

### 3. Configurer la clé API Claude

```bash
# Créer le secret Kubernetes pour Claude AI
kubectl create secret generic claude-api-key-secret \
  --from-literal=ANTHROPIC_API_KEY="ta-clé-api-ici"

# Vérifier que le secret est créé
kubectl get secrets
```

### 4. Construire les images Docker

```bash
# Image de l'API
docker build -t 2long2read-api:latest -f Dockerfile .

# Image du Worker
docker build -t 2long2read-worker:latest -f Dockerfile.worker .

# Vérifier les images
docker images | grep 2long2read
```

### 5. Déployer l'infrastructure sur Kubernetes

```bash
# Déployer MongoDB
kubectl apply -f k8s-infra.yaml

# Attendre que MongoDB soit prêt (environ 30 secondes)
kubectl wait --for=condition=ready pod -l app=mongo --timeout=120s

# Déployer l'API et le Worker
kubectl apply -f k8s-app.yaml

# Vérifier que tout tourne
kubectl get pods
```

**Sortie attendue :**
```
NAME                              READY   STATUS    RESTARTS   AGE
api-deployment-xxx                1/1     Running   0          30s
mongo-deployment-xxx              1/1     Running   0          60s
worker-deployment-xxx             1/1     Running   0          30s
```

### 6. Installer Prometheus + Grafana

```bash
# Ajouter le repo Helm de Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Installer Prometheus + Grafana (monitoring complet)
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --wait --timeout 5m

# Vérifier que tout est installé
kubectl get pods -n monitoring
```

**Sortie attendue :**
```
NAME                                                     READY   STATUS    RESTARTS   AGE
monitoring-grafana-xxx                                   3/3     Running   0          2m
monitoring-kube-prometheus-operator-xxx                  1/1     Running   0          2m
monitoring-kube-state-metrics-xxx                        1/1     Running   0          2m
monitoring-prometheus-node-exporter-xxx                  1/1     Running   0          2m
prometheus-monitoring-kube-prometheus-prometheus-0       2/2     Running   0          2m
```

### 7. Installer Airflow (Orchestration)

**⚠️ IMPORTANT : Airflow 2.10.3 avec Persistent Volume**

Airflow 3.0 a un bug avec les ConfigMaps Kubernetes (symlinks récursifs). Nous utilisons donc Airflow 2.10.3 avec un Persistent Volume pointant vers le dossier local `dags/`.

```bash
# Ajouter le repo Helm d'Airflow
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Créer le namespace Airflow
kubectl create namespace airflow

# Créer le Persistent Volume pour les DAGs
kubectl apply -f k8s-airflow-dags-pv.yaml

# Vérifier que le PV est créé
kubectl get pv airflow-dags-pv
kubectl get pvc airflow-dags-pvc -n airflow
```

**Sortie attendue :**
```
NAME              CAPACITY   ACCESS MODES   STATUS   CLAIM
airflow-dags-pv   1Gi        RWX            Bound    airflow/airflow-dags-pvc
```

**Installer Airflow avec le fichier de configuration :**

```bash
# Installer Airflow 2.10.3 avec PV pour les DAGs
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  -f airflow-values.yaml \
  --timeout 10m \
  --wait

# Attendre que tous les pods soient prêts (environ 3-5 minutes)
kubectl get pods -n airflow -w
```

**Sortie attendue (après 3-5 min) :**
```
NAME                                 READY   STATUS    RESTARTS   AGE
airflow-postgresql-0                 1/1     Running   0          3m
airflow-scheduler-xxx                3/3     Running   0          2m
airflow-triggerer-xxx                1/1     Running   0          2m
airflow-webserver-xxx                1/1     Running   0          2m
```

**Accéder à l'interface Airflow :**

```bash
# Port-forward vers Airflow UI
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080 &

# Ouvrir dans le navigateur : http://localhost:8080
# Username: admin
# Password: admin
```

**Vérifier que le DAG est chargé :**
1. Ouvre http://localhost:8080
2. Login avec `admin` / `admin`
3. Tu devrais voir le DAG `cgu_analysis_pipeline` avec 4 tasks :
   - ✅ check_environment
   - ✅ run_cgu_analysis
   - ✅ sync_metrics
   - ✅ final_report

---

## 🧪 Tester le Pipeline Complet

### Test Complet du Workflow End-to-End

**Objectif** : Analyser les CGU Spotify avec Claude AI, stocker dans MongoDB, synchroniser les métriques Prometheus, visualiser dans Grafana et orchestrer avec Airflow.

### Étape 1 : Port-forward MongoDB

```bash
# Ouvrir un port-forward vers MongoDB (laisser tourner dans un terminal)
kubectl port-forward -n default svc/mongo-service 27017:27017
```

### Étape 2 : Analyser le fichier Spotify avec le Worker

**Ouvrir un NOUVEAU terminal** et exécuter :

```bash
# Activer l'environnement Python
cd /chemin/vers/le/projet
source .venv/bin/activate

# Lancer l'analyse
cat raw_data/spotify_tc.txt | \
  MONGO_HOSTNAME=localhost MONGO_PORT=27017 \
  python worker.py \
  --task-id "spotify-demo-$(date +%s)" \
  --source-name "spotify" \
  --use-stdin
```

**Sortie attendue :**
```
[WORKER] Starting analysis task
[WORKER] Task ID: spotify-demo-1234567890
[WORKER] Source: spotify
[WORKER] Reading text content from stdin...
[WORKER] Text length: 54265 characters
[WORKER] Connecting to MongoDB at localhost:27017
[WORKER] MongoDB connection successful
[WORKER] Starting AI analysis...
[OK] spotify (Risk: 72/100)
[WORKER] Analysis completed successfully
[WORKER] Task finished and saved to MongoDB
```

### Étape 3 : Vérifier les données dans MongoDB

```bash
# Compter les analyses dans MongoDB
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --quiet --eval "db.analytic_reports.countDocuments()"

# Voir la dernière analyse Spotify
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --quiet --eval \
  "db.analytic_reports.findOne({source_name: 'spotify'}, {status: 1, 'report.risk_scores': 1})"
```

**Sortie attendue :**
```json
{
  "_id": ObjectId("..."),
  "status": "completed",
  "report": {
    "risk_scores": {
      "overall": 72,
      "data_privacy": 65,
      "termination_risk": 75,
      "legal_protection": 82,
      "transparency": 58
    }
  }
}
```

### Étape 4 : Synchroniser les métriques Prometheus

```bash
# Port-forward vers l'API (nouveau terminal ou en background)
kubectl port-forward -n default svc/api-service 8000:8000 &

# Attendre 3 secondes
sleep 3

# Synchroniser les métriques depuis MongoDB vers Prometheus
curl http://localhost:8000/api/v1/sync-metrics
```

**Sortie attendue :**
```json
{
  "message": "Metrics synchronized successfully",
  "stats": {
    "spotify": 1
  },
  "total": 1
}
```

### Étape 5 : Vérifier les métriques Prometheus

```bash
# Voir toutes les métriques Spotify
curl -s http://localhost:8000/metrics | grep 'source_name="spotify"'
```

**Sortie attendue :**
```
cgu_analyses_count{source_name="spotify"} 1.0
cgu_last_risk_score{source_name="spotify"} 72.0
cgu_data_privacy_score{source_name="spotify"} 65.0
cgu_termination_risk_score{source_name="spotify"} 75.0
cgu_legal_protection_score{source_name="spotify"} 82.0
cgu_transparency_score{source_name="spotify"} 58.0
cgu_problematic_clauses{source_name="spotify"} 10.0
```

### Étape 6 : Accéder à Grafana et visualiser

```bash
# Port-forward vers Grafana
kubectl port-forward -n monitoring svc/grafana 3000:80 &

# Ou utilise le script :
./access_grafana.sh
```

**Ouvre ton navigateur :**
- URL : http://localhost:3000
- Username : `admin`
- Password : `admin`

**Dans Grafana :**
1. Va dans "Explore" (icône boussole à gauche)
2. Sélectionne "Prometheus" comme source de données
3. Entre cette requête :
   ```
   cgu_last_risk_score{source_name="Spotify"}
   ```
4. Clique sur "Run query"
5. Tu devrais voir le score **72** !

**Sortie attendue dans Grafana :**
```
cgu_last_risk_score{source_name="Spotify"} = 72
cgu_data_privacy_score{source_name="Spotify"} = 65
cgu_termination_risk_score{source_name="Spotify"} = 75
cgu_problematic_clauses{source_name="Spotify"} = 10
```

### Étape 7 : Tester l'orchestration Airflow

**Port-forward vers Airflow UI :**

```bash
# Port-forward vers Airflow
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080 &
```

**Ouvre ton navigateur :**
- URL : http://localhost:8080
- Username : `admin`
- Password : `admin`

**Tester le DAG :**

1. Clique sur le DAG `cgu_analysis_pipeline` dans la liste
2. Clique sur le bouton "Trigger DAG" (icône play ▶️ en haut à droite)
3. Confirme en cliquant sur "Trigger"
4. Attends quelques secondes et rafraîchis la page

**Sortie attendue :**
- Les 4 tasks doivent être en vert (SUCCESS) :
  - ✅ check_environment
  - ✅ run_cgu_analysis
  - ✅ sync_metrics
  - ✅ final_report

**Voir les logs d'une task :**
1. Clique sur une task (ex: `run_cgu_analysis`)
2. Clique sur "Log"
3. Tu verras les détails de l'exécution avec les scores affichés

**Logs attendus pour `run_cgu_analysis` :**
```
===========================================
🤖 ANALYSE DES CGU EN COURS
===========================================

📄 Source : Spotify Terms & Conditions
📏 Longueur : ~54,000 caractères

🔄 Analyse avec Claude AI...

✅ Analyse terminée !

📊 RÉSULTATS :
   • Score global : 72/100 (Préoccupant)
   • Data Privacy : 65/100
   • Termination Risk : 75/100
   • Legal Protection : 82/100
   • Transparency : 58/100
   • Clauses dangereuses : 10

💾 Données sauvegardées dans MongoDB
```

---

## 🎯 Script de Test Rapide

Tu peux utiliser ce script bash pour tout tester d'un coup :

```bash
#!/bin/bash
# test_complete.sh

echo "🚀 Test complet du pipeline 2Long2Read"
echo "========================================"

# 1. Port-forward MongoDB
echo "1️⃣  Démarrage port-forward MongoDB..."
pkill -f "kubectl port-forward.*mongo" 2>/dev/null
kubectl port-forward -n default svc/mongo-service 27017:27017 > /dev/null 2>&1 &
sleep 3

# 2. Analyse Spotify
echo "2️⃣  Analyse des CGU Spotify..."
TASK_ID="test-$(date +%s)"
cat raw_data/spotify_tc.txt | \
  MONGO_HOSTNAME=localhost MONGO_PORT=27017 \
  .venv/bin/python worker.py \
  --task-id "$TASK_ID" \
  --source-name "spotify" \
  --use-stdin | grep "\[OK\]"

# 3. Vérification MongoDB
echo "3️⃣  Vérification MongoDB..."
COUNT=$(kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --quiet --eval \
  "db.analytic_reports.countDocuments({source_name: 'spotify'})")
echo "   ✅ Analyses Spotify dans MongoDB: $COUNT"

# 4. Port-forward API
echo "4️⃣  Démarrage port-forward API..."
pkill -f "kubectl port-forward.*api" 2>/dev/null
kubectl port-forward -n default svc/api-service 8000:8000 > /dev/null 2>&1 &
sleep 3

# 5. Sync métriques
echo "5️⃣  Synchronisation des métriques..."
curl -s http://localhost:8000/api/v1/sync-metrics | grep -o '"total":[0-9]*'

# 6. Vérification métriques
echo "6️⃣  Vérification des métriques Prometheus..."
curl -s http://localhost:8000/metrics | grep 'cgu_last_risk_score{source_name="spotify"}'

echo ""
echo "✅ Test terminé ! Accède à Grafana avec: ./access_grafana.sh"
echo "   URL: http://localhost:3000 (admin / prom-operator)"
```

Rends-le exécutable et lance-le :

```bash
chmod +x test_complete.sh
./test_complete.sh
```

---

## 📊 Résultats d'Analyse Spotify

L'analyse complète de Spotify révèle :

### Scores de Risque
- **Score Global** : 72/100 (Préoccupant)
- **Confidentialité des données** : 65/100
- **Risque de résiliation** : 75/100
- **Protection légale** : 82/100
- **Transparence** : 58/100

### Clauses Problématiques Identifiées (10 au total)
1. ⚠️ **Arbitrage obligatoire** (CRITIQUE) - Pas de recours collectifs
2. ⚠️ **Licence mondiale irrévocable** sur votre contenu
3. ⚠️ **Résiliation sans remboursement**
4. ⚠️ **Limitation de responsabilité** à 30$
5. Et 6 autres clauses à risque...

---

## 🏗️ Architecture du Projet

```
┌─────────────────┐
│  Fichier Spotify│
│  (raw_data/)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Worker Python  │
│  (Claude AI)    │◄─── Clé API Anthropic
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    MongoDB      │
│  (stockage)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API FastAPI   │
│  /metrics       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Prometheus    │
│  (scraping)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Grafana      │
│ (visualisation) │
└─────────────────┘
```

---

## 🔧 Commandes Utiles

### Vérifier l'état des pods

```bash
# Tous les pods
kubectl get pods --all-namespaces

# Pods de l'application
kubectl get pods -n default

# Pods de monitoring
kubectl get pods -n monitoring
```

### Redémarrer un composant

```bash
# Redémarrer l'API (après modification du code)
kubectl rollout restart deployment/api-deployment

# Redémarrer le Worker
kubectl rollout restart deployment/worker-deployment

# Attendre que le déploiement soit prêt
kubectl rollout status deployment/api-deployment
```

### Voir les logs

```bash
# Logs de l'API
kubectl logs -f deployment/api-deployment

# Logs du Worker
kubectl logs -f deployment/worker-deployment

# Logs de MongoDB
kubectl logs -f deployment/mongo-deployment
```

### Nettoyer MongoDB (repartir de zéro)

```bash
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --eval "db.analytic_reports.deleteMany({})"
```

---

## 🐛 Dépannage

### Problème : MongoDB inaccessible

```bash
# Vérifier que MongoDB tourne
kubectl get pods -l app=mongo

# Vérifier les logs
kubectl logs deployment/mongo-deployment

# Redémarrer MongoDB
kubectl rollout restart deployment/mongo-deployment
```

### Problème : Métriques à 0 dans Grafana

```bash
# 1. Vérifier que l'analyse est dans MongoDB
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --quiet --eval \
  "db.analytic_reports.countDocuments({source_name: 'spotify'})"

# 2. Re-synchroniser les métriques
curl http://localhost:8000/api/v1/sync-metrics

# 3. Vérifier les métriques dans Prometheus
curl http://localhost:8000/metrics | grep spotify
```

### Problème : Image Docker pas trouvée

```bash
# Vérifier que les images existent
docker images | grep 2long2read

# Si elles n'existent pas, les reconstruire
docker build -t 2long2read-api:latest -f Dockerfile .
docker build -t 2long2read-worker:latest -f Dockerfile.worker .

# Redémarrer les pods pour utiliser les nouvelles images
kubectl rollout restart deployment/api-deployment
kubectl rollout restart deployment/worker-deployment
```

---

## 🎓 Pour la Démo

### 1. Préparation (5 min avant)

```bash
# S'assurer que tout tourne
kubectl get pods --all-namespaces

# Port-forwards en place
kubectl port-forward -n default svc/mongo-service 27017:27017 &
kubectl port-forward -n default svc/api-service 8000:8000 &
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &

# Nettoyer MongoDB pour partir de zéro (optionnel)
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --eval "db.analytic_reports.deleteMany({})"
```

### 2. Démonstration Live (10 min)

**Étape 1 : Montrer le fichier d'entrée**
```bash
# Montrer les premières lignes du fichier Spotify
head -20 raw_data/spotify_tc.txt
wc -w raw_data/spotify_tc.txt  # Nombre de mots
```

**Étape 2 : Lancer l'analyse en direct**
```bash
cat raw_data/spotify_tc.txt | \
  MONGO_HOSTNAME=localhost MONGO_PORT=27017 \
  .venv/bin/python worker.py \
  --task-id "demo-live-$(date +%s)" \
  --source-name "spotify" \
  --use-stdin
```

**Étape 3 : Montrer les données dans MongoDB**
```bash
kubectl exec -n default deployment/mongo-deployment -- \
  mongosh too_long_to_read --quiet --eval \
  "db.analytic_reports.find({source_name: 'spotify'}).sort({_id: -1}).limit(1).pretty()"
```

**Étape 4 : Synchroniser et montrer les métriques**
```bash
# Sync
curl http://localhost:8000/api/v1/sync-metrics

# Voir les métriques
curl http://localhost:8000/metrics | grep spotify
```

**Étape 5 : Ouvrir Grafana**
- Navigateur : http://localhost:3000
- Login : admin / prom-operator
- Aller dans "Explore"
- Requête : `cgu_last_risk_score{source_name="spotify"}`
- Montrer le graphique avec le score de 72

### 3. Points à Souligner

✅ **Technologies utilisées** :
- Docker (conteneurisation)
- Kubernetes (orchestration)
- MongoDB (base de données)
- Claude AI (analyse IA)
- Prometheus (métriques)
- Grafana (visualisation)

✅ **Pipeline complet fonctionnel** :
- Fichier texte → Analyse IA → Stockage → Métriques → Visualisation

✅ **Scores de risque précis** :
- Analyse sémantique approfondie des CGU
- Identification des clauses dangereuses
- Recommandations pour les utilisateurs

---

## 📁 Structure du Projet

```
.
├── README.md                  # Ce fichier
├── requirements.txt           # Dépendances Python
├── Dockerfile                 # Image Docker de l'API
├── Dockerfile.worker          # Image Docker du Worker
├── main.py                    # API FastAPI avec métriques Prometheus
├── worker.py                  # Worker d'analyse (Claude AI)
├── ai_analyzer.py             # Logique d'analyse IA
├── k8s-app.yaml              # Déploiement API + Worker
├── k8s-infra.yaml            # Déploiement MongoDB
├── access_grafana.sh          # Script d'accès Grafana
├── raw_data/
│   └── spotify_tc.txt         # Fichier de test Spotify
└── config/
    └── grafana_spotify_dashboard.json  # Dashboard Grafana
```

---

## 🚀 Prochaines Étapes

Une fois que tout fonctionne chez toi, tu peux :

1. **Analyser d'autres fichiers** : Ajoute tes propres fichiers T&C dans `raw_data/`
2. **Créer des dashboards Grafana** : Importe `config/grafana_spotify_dashboard.json`
3. **Intégrer Airflow** : Pour l'orchestration automatique (à venir)
4. **Ajouter d'autres sources** : Google, Facebook, Amazon, etc.

---

## 📞 Support

Si tu rencontres des problèmes :

1. Vérifie que Docker Desktop est démarré
2. Vérifie que tous les pods sont en état `Running`
3. Vérifie les logs des pods concernés
4. Consulte la section "Dépannage" ci-dessus

---

## ✨ Résumé des Commandes Essentielles

```bash
# Setup initial
kubectl create secret generic claude-api-key-secret --from-literal=ANTHROPIC_API_KEY="ta-clé"
docker build -t 2long2read-api:latest -f Dockerfile .
docker build -t 2long2read-worker:latest -f Dockerfile.worker .
kubectl apply -f k8s-infra.yaml
kubectl apply -f k8s-app.yaml
helm install monitoring prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# Test complet
kubectl port-forward -n default svc/mongo-service 27017:27017 &
cat raw_data/spotify_tc.txt | MONGO_HOSTNAME=localhost MONGO_PORT=27017 .venv/bin/python worker.py --task-id "test-$(date +%s)" --source-name "spotify" --use-stdin
kubectl port-forward -n default svc/api-service 8000:8000 &
curl http://localhost:8000/api/v1/sync-metrics
./access_grafana.sh
```

---

**Bon courage pour ta démo ! 🎉**
