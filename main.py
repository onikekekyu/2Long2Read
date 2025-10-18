import os
import requests
import base64
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from pymongo import MongoClient
import uuid

# --- Database Connection ---
MONGO_HOSTNAME = os.environ.get("MONGO_HOSTNAME", "localhost")
client = MongoClient(f"mongodb://{MONGO_HOSTNAME}:27017")
db = client.too_long_to_read
collection = db.analytic_reports

# --- Airflow Configuration ---
# URL de l'API Airflow (via port-forward en local, ou service K8s en prod)
# Note: Airflow 3.0+ uses /api/v2 instead of /api/v1
AIRFLOW_URL = os.environ.get(
    "AIRFLOW_URL",
    "http://localhost:8080/api/v2/dags/cgu_analysis_pipeline/dagRuns"
)

# Authentification Airflow (admin:admin par défaut)
airflow_username = os.environ.get("AIRFLOW_USERNAME", "admin")
airflow_password = os.environ.get("AIRFLOW_PASSWORD", "admin")
auth_string = f"{airflow_username}:{airflow_password}"
auth_b64 = base64.b64encode(auth_string.encode()).decode()

AIRFLOW_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "Authorization": f"Basic {auth_b64}",
}

app = FastAPI(
    title="2Long2Read API",
    description="API pour analyser les Terms & Conditions avec Airflow + Claude AI",
    version="2.0.0"
)


class AnalysisRequest(BaseModel):
    content: str = Field(..., min_length=100, description="Le texte des T&C à analyser")
    source_name: str = Field(default="api_upload", description="Nom de la source")


def trigger_airflow_dag(task_id: str, content: str, source_name: str):
    """
    Déclenche le DAG Airflow pour lancer l'analyse.
    Fonction exécutée en tâche de fond pour ne pas bloquer la réponse API.
    """
    payload = {
        "conf": {
            "task_id": task_id,
            "text_content": content,
            "source_name": source_name,
        }
    }

    try:
        print(f"[API] Triggering Airflow DAG for task {task_id}...")
        response = requests.post(
            AIRFLOW_URL,
            headers=AIRFLOW_HEADERS,
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
        print(f"[ERROR] Failed to trigger Airflow DAG for task {task_id}: {e}")

        # Mettre à jour le statut en DB pour indiquer l'échec
        collection.update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "failed_to_trigger",
                "error_message": f"Failed to trigger Airflow: {str(e)}"
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
    """
    document = collection.find_one({"task_id": task_id}, {'_id': 0})

    if document:
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
