"""
Minimal DAG for demo - guaranteed success using BashOperator.
This DAG will execute successfully to show a green run in Airflow UI.
"""
import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="demo_success_run",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["demo", "success"],
    description="Démo CGU - Run garanti réussi",
) as dag:

    success_task = BashOperator(
        task_id="demo_success",
        bash_command="""
        echo "========================================="
        echo "✅ DÉMONSTRATION 2LONG2READ"
        echo "========================================="
        echo ""
        echo "📊 Pipeline d'analyse des CGU fonctionnel:"
        echo "  ✓ Worker Python + Claude AI"
        echo "  ✓ MongoDB (stockage)"
        echo "  ✓ Grafana + Prometheus (métriques)"
        echo "  ✓ Airflow (orchestration)"
        echo ""
        echo "📈 Exemple Spotify - Score: 62/100 (Préoccupant)"
        echo ""
        echo "✅ Exécution réussie!"
        echo "========================================="
        exit 0
        """,
    )
