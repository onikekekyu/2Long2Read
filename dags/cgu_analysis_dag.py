from __future__ import annotations
import pendulum
from airflow.models.dag import DAG
from airflow.providers.cncf.kubernetes.operators.kubernetes_pod import KubernetesPodOperator

with DAG(
    dag_id="cgu_analysis_pipeline",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None, # Ce DAG sera déclenché manuellement par notre API
    tags=["2long2read"],
) as dag:
    # Cette tâche lance un pod K8s en utilisant l'image de notre worker
    analysis_task = KubernetesPodOperator(
        task_id="run_cgu_analysis",
        name="cgu-analysis-pod",
        namespace="default", # ou 'airflow' si vous préférez
        image="2long2read-worker:latest", # On réutilise l'image déjà construite !
        image_pull_policy="Never",
        # On passe le texte et l'ID de la tâche en arguments de la commande
        cmds=["python", "worker.py"],
        arguments=[
            "--task-id", "{{ dag_run.conf['task_id'] }}",
            "--text-content", "{{ dag_run.conf['text_content'] }}",
            "--source-name", "{{ dag_run.conf['source_name'] }}"
        ],
        # On attache le secret de la clé d'API
        secrets=[
            Secret(
                deploy_type="env",
                deploy_target="ANTHROPIC_API_KEY",
                secret="claude-api-key-secret",
                key="ANTHROPIC_API_KEY"
            )
        ],
        # On s'assure que le pod est supprimé après exécution
        do_xcom_push=False,
        get_logs=True,
    )