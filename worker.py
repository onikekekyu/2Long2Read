#!/usr/bin/env python3
"""
Worker CLI pour analyse de Terms & Conditions.
Conçu pour être exécuté comme un job Kubernetes par Airflow.
"""
import os
import sys
import argparse
import traceback
from pymongo import MongoClient
from ai_analyzer import analyze_text_content


def main():
    # --- 1. Parser les arguments de la ligne de commande ---
    parser = argparse.ArgumentParser(description="Run a single T&C analysis task.")
    parser.add_argument("--task-id", required=True, help="The unique ID for this task")
    parser.add_argument("--source-name", default="airflow_trigger", help="Source name")

    # IMPORTANT: Pour les longs textes, on lit depuis stdin au lieu d'un argument
    parser.add_argument("--use-stdin", action="store_true",
                       help="Read text content from stdin (for long texts)")
    parser.add_argument("--text-content", help="Text content (for short texts only)")

    args = parser.parse_args()

    print(f"[WORKER] Starting analysis task", file=sys.stderr)
    print(f"[WORKER] Task ID: {args.task_id}", file=sys.stderr)
    print(f"[WORKER] Source: {args.source_name}", file=sys.stderr)

    # --- 2. Récupérer le contenu texte ---
    if args.use_stdin:
        print("[WORKER] Reading text content from stdin...", file=sys.stderr)
        text_content = sys.stdin.read()
    elif args.text_content:
        text_content = args.text_content
    else:
        print("[ERROR] No text content provided (use --text-content or --use-stdin)", file=sys.stderr)
        sys.exit(1)

    print(f"[WORKER] Text length: {len(text_content)} characters", file=sys.stderr)

    # --- 3. Connexion à MongoDB ---
    mongo_hostname = os.environ.get("MONGO_HOSTNAME", "localhost")
    mongo_port = int(os.environ.get("MONGO_PORT", "27017"))

    print(f"[WORKER] Connecting to MongoDB at {mongo_hostname}:{mongo_port}", file=sys.stderr)

    try:
        client = MongoClient(
            f"mongodb://{mongo_hostname}:{mongo_port}",
            serverSelectionTimeoutMS=10000,  # 10 secondes timeout
            connectTimeoutMS=10000
        )
        # Test de connexion
        client.server_info()
        print("[WORKER] MongoDB connection successful", file=sys.stderr)

        db = client.too_long_to_read
        collection = db.analytic_reports

    except Exception as e:
        print(f"[ERROR] Failed to connect to MongoDB: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

    # --- 4. Exécuter l'analyse ---
    try:
        # Mettre à jour le statut
        result = collection.update_one(
            {"task_id": args.task_id},
            {"$set": {"status": "in_progress_from_airflow"}},
            upsert=True  # Créer si n'existe pas
        )
        print(f"[WORKER] Status updated (matched: {result.matched_count}, modified: {result.modified_count})", file=sys.stderr)

        # Lancer l'analyse
        print(f"[WORKER] Starting AI analysis...", file=sys.stderr)
        analysis_report = analyze_text_content(text_content, args.source_name)

        if "error" in analysis_report:
            raise Exception(analysis_report["error"])

        print("[WORKER] Analysis completed successfully", file=sys.stderr)

        # Sauvegarder le rapport
        collection.update_one(
            {"task_id": args.task_id},
            {"$set": {
                "status": "completed",
                "report": analysis_report
            }}
        )
        print(f"[WORKER] Task {args.task_id} finished and saved to MongoDB", file=sys.stderr)
        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}", file=sys.stderr)
        traceback.print_exc()

        try:
            collection.update_one(
                {"task_id": args.task_id},
                {"$set": {
                    "status": "failed",
                    "error_message": str(e)
                }}
            )
        except Exception as db_error:
            print(f"[ERROR] Failed to update error status in DB: {db_error}", file=sys.stderr)

        sys.exit(1)


if __name__ == "__main__":
    main()
