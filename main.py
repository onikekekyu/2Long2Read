import os
import requests
import base64
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from pymongo import MongoClient
import uuid
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Gauge, Histogram

# --- Database Connection ---
MONGO_HOSTNAME = os.environ.get("MONGO_HOSTNAME", "localhost")
client = MongoClient(f"mongodb://{MONGO_HOSTNAME}:27017")
db = client.too_long_to_read
collection = db.analytic_reports

# --- Airflow Configuration ---
# URL de l'API Airflow via service Kubernetes (cross-namespace)
# Note: Airflow 3.0+ uses JWT authentication
AIRFLOW_BASE_URL = os.environ.get(
    "AIRFLOW_BASE_URL",
    "http://airflow-api-server.airflow.svc.cluster.local:8080"
)
AIRFLOW_URL = f"{AIRFLOW_BASE_URL}/api/v2/dags/cgu_analysis_pipeline/dagRuns"
AIRFLOW_TOKEN_URL = f"{AIRFLOW_BASE_URL}/auth/token"

# Authentification Airflow (admin:admin par défaut)
airflow_username = os.environ.get("AIRFLOW_USERNAME", "admin")
airflow_password = os.environ.get("AIRFLOW_PASSWORD", "admin")

# Cache pour le JWT token (in-memory, simple)
_airflow_jwt_token = None
_airflow_jwt_expiry = 0

def get_airflow_jwt_token():
    """
    Obtient un JWT token d'Airflow pour l'authentification API.
    Cache le token jusqu'à expiration (1 heure par défaut).
    """
    global _airflow_jwt_token, _airflow_jwt_expiry
    import time

    # Si le token existe et n'est pas expiré, le réutiliser
    if _airflow_jwt_token and time.time() < _airflow_jwt_expiry:
        return _airflow_jwt_token

    # Sinon, obtenir un nouveau token
    try:
        print(f"[API] Requesting new JWT token from Airflow...")
        response = requests.post(
            AIRFLOW_TOKEN_URL,
            json={
                "username": airflow_username,
                "password": airflow_password
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        _airflow_jwt_token = data.get("access_token")
        # Token valide pendant 55 minutes (expire après 1h, mais on rafraîchit avant)
        _airflow_jwt_expiry = time.time() + (55 * 60)

        print(f"[API] JWT token obtained successfully")
        return _airflow_jwt_token

    except Exception as e:
        print(f"[ERROR] Failed to get JWT token from Airflow: {e}")
        return None

app = FastAPI(
    title="2Long2Read API",
    description="API pour analyser les Terms & Conditions avec Airflow + Claude AI",
    version="2.0.0"
)

# Activer le monitoring Prometheus (expose automatiquement /metrics)
Instrumentator().instrument(app).expose(app)

# ═══════════════════════════════════════════════════════════════
# MÉTRIQUES PROMETHEUS CUSTOM POUR LES ANALYSES CGU
# ═══════════════════════════════════════════════════════════════

# Nombre total d'analyses soumises (via API)
cgu_analyses_total = Counter(
    'cgu_analyses_total',
    'Nombre total d\'analyses CGU soumises via API',
    ['source_name']
)

# Nombre total d'analyses complétées (depuis MongoDB)
cgu_analyses_count = Gauge(
    'cgu_analyses_count',
    'Nombre total d\'analyses CGU complétées (depuis MongoDB)',
    ['source_name']
)

# Dernier score de risque global mesuré
cgu_last_risk_score = Gauge(
    'cgu_last_risk_score',
    'Dernier score de risque global (0-100)',
    ['source_name']
)

# Distribution des scores de risque
cgu_risk_score_histogram = Histogram(
    'cgu_risk_score',
    'Distribution des scores de risque',
    buckets=[0, 20, 40, 60, 80, 100]
)

# Scores par catégorie (les 6 dimensions du projet)
cgu_data_privacy_score = Gauge(
    'cgu_data_privacy_score',
    'Score de risque: Partage de données (0-100)',
    ['source_name']
)

cgu_intellectual_property_score = Gauge(
    'cgu_intellectual_property_score',
    'Score de risque: Propriété intellectuelle (0-100)',
    ['source_name']
)

cgu_termination_risk_score = Gauge(
    'cgu_termination_risk_score',
    'Score de risque: Résiliation abusive (0-100)',
    ['source_name']
)

cgu_legal_protection_score = Gauge(
    'cgu_legal_protection_score',
    'Score de risque: Protection légale (0-100)',
    ['source_name']
)

cgu_transparency_score = Gauge(
    'cgu_transparency_score',
    'Score de risque: Transparence (0-100)',
    ['source_name']
)

cgu_liability_score = Gauge(
    'cgu_liability_score',
    'Score de risque: Responsabilité (0-100)',
    ['source_name']
)

# Nombre de clauses problématiques détectées
cgu_problematic_clauses = Gauge(
    'cgu_problematic_clauses',
    'Nombre de clauses problématiques détectées',
    ['source_name']
)

# Temps d'analyse (en secondes)
cgu_analysis_duration = Histogram(
    'cgu_analysis_duration_seconds',
    'Durée d\'analyse en secondes',
    buckets=[5, 10, 15, 30, 60, 120]
)


class AnalysisRequest(BaseModel):
    content: str = Field(..., min_length=100, description="Le texte des T&C à analyser")

    source_name: str = Field(default="api_upload", description="Nom de la source")


def trigger_airflow_dag(task_id: str, content: str, source_name: str):
    """
    Déclenche le DAG Airflow pour lancer l'analyse.
    Fonction exécutée en tâche de fond pour ne pas bloquer la réponse API.
    Utilise JWT authentication pour Airflow 3.0+.
    """
    from datetime import datetime, timezone

    payload = {
        "logical_date": datetime.now(timezone.utc).isoformat(),
        "conf": {
            "task_id": task_id,
            "text_content": content,
            "source_name": source_name,
        }
    }

    try:
        # Obtenir un JWT token pour l'authentification
        jwt_token = get_airflow_jwt_token()
        if not jwt_token:
            raise Exception("Unable to obtain JWT token from Airflow")

        # Headers avec JWT token
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Authorization": f"Bearer {jwt_token}",
        }

        print(f"[API] Triggering Airflow DAG for task {task_id}...")
        response = requests.post(
            AIRFLOW_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        print(f"[API] Airflow DAG triggered successfully for task {task_id}")
        print(f"[API] Response: {response.json()}")

        # Mettre à jour le statut pour indiquer que c'est envoyé à Airflow
        collection.update_one(
            {"task_id": task_id},
            {"$set": {"status": "queued_in_airflow"}}
        )

    except requests.exceptions.RequestException as e:
        # Log detailed error including response body if available
        error_details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.text
                print(f"[ERROR] Airflow response body: {error_body}")
                error_details = f"{str(e)} - Response: {error_body}"
            except:
                pass

        print(f"[ERROR] Failed to trigger Airflow DAG for task {task_id}: {error_details}")

        # Mettre à jour le statut en DB pour indiquer l'échec
        collection.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "failed_to_trigger",
                "error_message": f"Failed to trigger Airflow: {error_details[:500]}"
            }}
        )


@app.post("/api/v1/analyze")
async def submit_for_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Soumet une analyse de Terms & Conditions.
    Crée une tâche en DB et la soumet à Airflow via son API.
    """
    task_id = str(uuid.uuid4())

    # 1. Créer la tâche en base de données
    document = {
        "task_id": task_id,
        "source_name": request.source_name,
        "status": "pending",
        "report": None
    }
    collection.insert_one(document)
    print(f"[API] Created task {task_id} in MongoDB")

    # 📊 Mettre à jour les métriques Prometheus
    cgu_analyses_total.labels(source_name=request.source_name).inc()

    # 2. Déclencher le DAG Airflow en tâche de fond
    background_tasks.add_task(
        trigger_airflow_dag,
        task_id,
        request.content,
        request.source_name
    )

    return {
        "message": "Analysis task has been accepted and queued in Airflow",
        "task_id": task_id,
        "status_url": f"/api/v1/report/{task_id}"
    }


@app.get("/api/v1/report/{task_id}")
def get_report(task_id: str):
    """
    Récupère le rapport d'analyse pour un task_id donné.
    Met à jour les métriques Prometheus si le rapport est terminé.
    """
    document = collection.find_one({"task_id": task_id}, {'_id': 0})

    if document:
        # 📊 Si le rapport est terminé, mettre à jour les métriques Prometheus
        if document.get("status") == "completed" and document.get("report"):
            report = document["report"]
            source_name = document.get("source_name", "unknown")

            # Scores de risque
            risk_scores = report.get("risk_scores", {})

            # Score global
            overall_score = risk_scores.get("overall", 0)
            cgu_last_risk_score.labels(source_name=source_name).set(overall_score)
            cgu_risk_score_histogram.observe(overall_score)

            # Scores par catégorie (adaptez les clés selon votre worker.py)
            cgu_data_privacy_score.labels(source_name=source_name).set(
                risk_scores.get("data_privacy", 0)
            )
            cgu_intellectual_property_score.labels(source_name=source_name).set(
                risk_scores.get("intellectual_property", 0)
            )
            cgu_termination_risk_score.labels(source_name=source_name).set(
                risk_scores.get("termination_risk", 0)
            )
            cgu_legal_protection_score.labels(source_name=source_name).set(
                risk_scores.get("legal_protection", 0)
            )
            cgu_transparency_score.labels(source_name=source_name).set(
                risk_scores.get("transparency", 0)
            )
            cgu_liability_score.labels(source_name=source_name).set(
                risk_scores.get("liability", 0)
            )

            # Nombre de clauses problématiques
            problematic_clauses = report.get("problematic_clauses_count", 0)
            cgu_problematic_clauses.labels(source_name=source_name).set(problematic_clauses)

        return document
    else:
        raise HTTPException(status_code=404, detail="Report not found")


@app.get("/health")
def health_check():
    """Endpoint de santé pour vérifier que l'API fonctionne."""
    try:
        # Vérifier la connexion MongoDB
        client.server_info()
        return {"status": "healthy", "mongodb": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/api/v1/sync-metrics")
def sync_metrics():
    """
    Synchronise les métriques Prometheus avec les données réelles de MongoDB.
    Compte tous les documents par source_name et met à jour les métriques détaillées.
    """
    try:
        # Compter les documents par source_name
        pipeline = [
            {"$match": {"status": "completed"}},  # Seulement les analyses terminées
            {"$group": {"_id": "$source_name", "count": {"$sum": 1}}}
        ]

        results = list(collection.aggregate(pipeline))

        stats = {}
        for doc in results:
            source = doc["_id"] if doc["_id"] else "unknown"
            count = doc["count"]
            stats[source] = count

            # Mettre à jour le Gauge Prometheus (on peut set la valeur directement)
            cgu_analyses_count.labels(source_name=source).set(count)

        # Récupérer la dernière analyse de chaque source pour les scores détaillés
        for source_name in stats.keys():
            latest = collection.find_one(
                {"source_name": source_name, "status": "completed"},
                sort=[("_id", -1)]  # Tri par _id décroissant (plus récent)
            )

            if latest and "report" in latest:
                report = latest["report"]

                # Scores de risque
                if "risk_scores" in report:
                    scores = report["risk_scores"]
                    if "overall" in scores:
                        cgu_last_risk_score.labels(source_name=source_name).set(scores["overall"])
                    if "data_privacy" in scores:
                        cgu_data_privacy_score.labels(source_name=source_name).set(scores["data_privacy"])
                    if "termination_risk" in scores:
                        cgu_termination_risk_score.labels(source_name=source_name).set(scores["termination_risk"])
                    if "legal_protection" in scores:
                        cgu_legal_protection_score.labels(source_name=source_name).set(scores["legal_protection"])
                    if "transparency" in scores:
                        cgu_transparency_score.labels(source_name=source_name).set(scores["transparency"])

                # Nombre de clauses dangereuses
                if "dangerous_clauses" in report:
                    cgu_problematic_clauses.labels(source_name=source_name).set(len(report["dangerous_clauses"]))

        return {
            "message": "Metrics synchronized successfully",
            "stats": stats,
            "total": sum(stats.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync metrics: {str(e)}")


@app.get("/")
def root():
    """Page d'accueil de l'API."""
    return {
        "message": "2Long2Read API - Analyse de Terms & Conditions",
        "version": "2.0.0 (Airflow-powered)",
        "endpoints": {
            "analyze": "POST /api/v1/analyze",
            "get_report": "GET /api/v1/report/{task_id}",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }
