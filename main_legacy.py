import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
import uuid
import pika
import json

# --- Database Connection ---
MONGO_HOSTNAME = os.environ.get("MONGO_HOSTNAME", "localhost")
client = MongoClient(f"mongodb://{MONGO_HOSTNAME}:27017")
db = client.too_long_to_read
collection = db.analytic_reports

# --- RabbitMQ Connection ---
RABBITMQ_HOSTNAME = os.environ.get("RABBITMQ_HOSTNAME", "localhost")
connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOSTNAME))
channel = connection.channel()
channel.queue_declare(queue='analysis_tasks', durable=True)

app = FastAPI()

# CHANGE HERE: The request now expects a 'content' field instead of 'url'
class AnalysisRequest(BaseModel):
    content: str = Field(..., min_length=100) # Expects text, with a minimum length
    source_name: str = "text_upload" # Optional: a name for the source text

@app.post("/api/v1/analyze")
def submit_for_analysis(request: AnalysisRequest):
    """
    Accepts raw text content, creates a task in the DB, and publishes a message.
    """
    task_id = str(uuid.uuid4())
    
    # CHANGE HERE: The document no longer stores a 'url'
    document = {
        "task_id": task_id,
        "source_name": request.source_name,
        "status": "pending",
        "report": None
    }
    collection.insert_one(document)

    # CHANGE HERE: The message for the worker now contains the full text content
    message_body = {
        "task_id": task_id,
        "text_content": request.content, # Send the actual text
        "source_name": request.source_name # Send the source name to the worker
    }

    channel.basic_publish(
        exchange='',
        routing_key='analysis_tasks',
        body=json.dumps(message_body),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    
    print(f" [x] Sent message for task_id: {task_id}")
    return {"message": "Analysis task has been queued successfully", "task_id": task_id}

@app.get("/api/v1/report/{task_id}")
def get_report(task_id: str):
    document = collection.find_one({"task_id": task_id}, {'_id': 0})
    if document:
        return document
    else:
        raise HTTPException(status_code=404, detail="Report not found")

@app.on_event("shutdown")
def shutdown_event():
    connection.close()