# Votre fichier worker.py mis à jour
import os
import pika
import json
from pymongo import MongoClient

# CHANGE ICI: On importe la nouvelle fonction
from ai_analyzer import analyze_text_content

# --- Connexions (ne change pas) ---
MONGO_HOSTNAME = os.environ.get("MONGO_HOSTNAME", "localhost")
client = MongoClient(f"mongodb://{MONGO_HOSTNAME}:27017")
db = client.too_long_to_read
collection = db.analytic_reports

RABBITMQ_HOSTNAME = os.environ.get("RABBITMQ_HOSTNAME", "localhost")
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOSTNAME))
channel = connection.channel()
channel.queue_declare(queue='analysis_tasks', durable=True)
print(' [*] Worker is waiting for messages. To exit press CTRL+C')

def callback(ch, method, properties, body):
    message = json.loads(body)
    task_id = message["task_id"]
    text_content = message["text_content"]
    source_name = message.get("source_name", "Unknown Upload") # On récupère le nom de la source

    print(f" [✔] Received task {task_id} for source: {source_name}")

    try:
        collection.update_one({"task_id": task_id}, {"$set": {"status": "in_progress"}})

        # APPEL DE LA NOUVELLE FONCTION
        analysis_report = analyze_text_content(text_content, source_name)

        if "error" in analysis_report:
            raise Exception(analysis_report["error"])

        print(" [i] Analysis complete.")

        collection.update_one(
            {"task_id": task_id},
            {"$set": {"status": "completed", "report": analysis_report}}
        )
        print(f" [✔] Task {task_id} finished and report saved to DB.")

    except Exception as e:
        print(f" [!] An error occurred with task {task_id}: {e}")
        collection.update_one({"task_id": task_id}, {"$set": {"status": "failed", "error_message": str(e)}})

    ch.basic_ack(delivery_tag=method.delivery_tag)

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='analysis_tasks', on_message_callback=callback)
channel.start_consuming()