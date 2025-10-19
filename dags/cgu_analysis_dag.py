"""
DAG Airflow pour l'analyse de Terms & Conditions.
Uses KubernetesPodOperator - the proper way to run pods from Airflow!
"""
import pendulum
from airflow.models.dag import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.operators.bash import BashOperator
from kubernetes.client import models as k8s

with DAG(
    dag_id="cgu_analysis_pipeline",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["2long2read", "tc-analysis"],
    description="Analyse des Terms & Conditions avec Claude AI",
) as dag:

    # Task 1: Run analysis using KubernetesPodOperator
    # NOTE: This DAG is designed to be triggered via API with parameters:
    #   - task_id: Unique identifier for the analysis
    #   - text_content: The T&C text to analyze (min 100 chars)
    #   - source_name: Name of the company/source
    #
    # If triggered from UI without parameters, it will use a test document.
    run_analysis = KubernetesPodOperator(
        task_id="run_cgu_analysis",
        name="cgu-analysis-worker",
        namespace="airflow",
        image="2long2read-worker:latest",
        image_pull_policy="IfNotPresent",
        cmds=["python3"],
        arguments=[
            "/app/worker.py",
            "--task-id", "{{ dag_run.conf.get('task_id', 'manual-ui-trigger-' + ts_nodash) }}",
            "--source-name", "{{ dag_run.conf.get('source_name', 'manual_ui_test') }}",
            "--text-content", "{{ dag_run.conf.get('text_content', 'TEST TERMS AND CONDITIONS: This is a minimal test document used when triggering from Airflow UI. By using this service, you agree to our terms. We collect your data. We may terminate your account at any time. You waive all legal rights. This is only a test to verify the pipeline works correctly.')[:50000] }}",
        ],
        env_vars={
            "MONGO_HOSTNAME": "mongo-service.default.svc.cluster.local",
            "MONGO_PORT": "27017",
            "ANTHROPIC_API_KEY": "{{ var.value.get('ANTHROPIC_API_KEY', '') }}",
        },
        get_logs=True,
        is_delete_operator_pod=False,  # Keep pod for debugging
        in_cluster=True,  # Running inside Kubernetes cluster
        startup_timeout_seconds=600,  # Allow 10 minutes for Claude API
    )

    # Task 2: Log completion (simplified - kubectl not available in Airflow pods)
    log_completion = BashOperator(
        task_id="log_completion",
        bash_command="""
        TASK_ID="{{ dag_run.conf.get('task_id', 'unknown-task') }}"
        SOURCE_NAME="{{ dag_run.conf.get('source_name', 'unknown') }}"

        echo "========================================="
        echo "CGU Analysis Pipeline Completed"
        echo "========================================="
        echo "Task ID: $TASK_ID"
        echo "Source: $SOURCE_NAME"
        echo ""
        echo "✅ Analysis completed and saved to MongoDB"
        echo "📊 View metrics at: http://api-service:8000/metrics"
        echo "🔍 Check Grafana dashboard for visualization"
        echo "========================================="
        """,
    )

    # Define task dependencies
    run_analysis >> log_completion
