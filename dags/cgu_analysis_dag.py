"""
DAG Airflow pour l'analyse de Terms & Conditions.
Uses BashOperator to run kubectl commands directly - works with Airflow 3.0!
"""
import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="cgu_analysis_pipeline",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["2long2read", "tc-analysis"],
    description="Analyse des Terms & Conditions avec Claude AI",
) as dag:

    # Task 1: Create and run the analysis pod
    run_analysis = BashOperator(
        task_id="run_cgu_analysis",
        bash_command="""
        # Get configuration from dag_run.conf
        TASK_ID="{{ dag_run.conf.get('task_id', 'unknown-task') }}"
        SOURCE_NAME="{{ dag_run.conf.get('source_name', 'airflow_trigger') }}"
        TEXT_CONTENT="{{ (dag_run.conf.get('text_content', ''))[:50000] }}"

        echo "Starting T&C Analysis"
        echo "Task ID: $TASK_ID"
        echo "Source: $SOURCE_NAME"

        # Create unique pod name
        POD_NAME="cgu-analysis-airflow-$(date +%s)-$RANDOM"

        # Run the worker pod
        kubectl run "$POD_NAME" \
          --image=2long2read-worker:latest \
          --namespace=airflow \
          --restart=Never \
          --image-pull-policy=IfNotPresent \
          --env="MONGO_HOSTNAME=mongo-service.default.svc.cluster.local" \
          --env="MONGO_PORT=27017" \
          --env="ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
          -- python3 /app/worker.py \
             --task-id "$TASK_ID" \
             --source-name "$SOURCE_NAME" \
             --text-content "$TEXT_CONTENT"

        # Wait for pod to be ready
        echo "Waiting for pod to start..."
        kubectl wait --for=condition=Ready pod/"$POD_NAME" --namespace=airflow --timeout=30s || true
        sleep 2

        # Follow logs
        echo "Analysis in progress..."
        kubectl logs -f "$POD_NAME" --namespace=airflow

        # Check if analysis completed successfully
        POD_STATUS=$(kubectl get pod "$POD_NAME" --namespace=airflow -o jsonpath='{.status.phase}')

        if [ "$POD_STATUS" = "Succeeded" ]; then
            echo "✅ Analysis completed successfully!"
            exit 0
        else
            echo "❌ Analysis failed with status: $POD_STATUS"
            kubectl logs "$POD_NAME" --namespace=airflow --tail=50
            exit 1
        fi
        """,
        env={
            "ANTHROPIC_API_KEY": "{{ var.value.get('ANTHROPIC_API_KEY', '') }}",
        },
    )

    # Task 2: Retrieve and display results
    get_results = BashOperator(
        task_id="get_analysis_results",
        bash_command="""
        TASK_ID="{{ dag_run.conf.get('task_id', 'unknown-task') }}"

        echo "Retrieving results for task: $TASK_ID"

        # Query MongoDB for results
        kubectl exec mongo-deployment-869dd489bf-bfwgx --namespace default -- \
          mongosh too_long_to_read --quiet --eval \
          "printjson(db.analytic_reports.findOne({\"task_id\": \"$TASK_ID\"}, {\"_id\": 0, \"task_id\": 1, \"status\": 1, \"report.risk_scores\": 1, \"report.executive_summary.overall_verdict\": 1}))"

        echo "✅ Results retrieved successfully!"
        """,
    )

    # Define task dependencies
    run_analysis >> get_results
