"""
DAG Airflow SIMPLIFIÉ pour la démonstration.
Cette version utilise uniquement des BashOperators simples qui RÉUSSISSENT à coup sûr.
"""
import pendulum
from airflow.models.dag import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="cgu_analysis_demo",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["2long2read", "demo"],
    description="Pipeline de démonstration - Analyse de CGU simplifiée",
) as dag:

    # Task 1: Simulation de l'analyse
    simulate_analysis = BashOperator(
        task_id="simulate_cgu_analysis",
        bash_command="""
        echo "========================================="
        echo "🔍 ANALYSE DES CGU EN COURS..."
        echo "========================================="
        echo ""
        echo "📄 Source: Spotify Terms & Conditions"
        echo "📏 Longueur: 54,265 caractères"
        echo ""
        echo "🤖 Utilisation de Claude AI pour l'analyse..."
        sleep 2
        echo "✅ Analyse terminée avec succès"
        echo ""
        echo "📊 RÉSULTATS:"
        echo "  • Score de risque global: 62/100"
        echo "  • Verdict: Concerning (Préoccupant)"
        echo "  • Clauses critiques identifiées: 4"
        echo ""
        echo "💾 Sauvegarde dans MongoDB..."
        sleep 1
        echo "✅ Données sauvegardées avec succès"
        echo ""
        echo "========================================="
        """,
    )

    # Task 2: Simulation du stockage MongoDB
    simulate_storage = BashOperator(
        task_id="simulate_mongodb_storage",
        bash_command="""
        echo "========================================="
        echo "💾 STOCKAGE DES RÉSULTATS"
        echo "========================================="
        echo ""
        echo "Base de données: too_long_to_read"
        echo "Collection: analytic_reports"
        echo ""
        echo "Document inséré:"
        echo "  • task_id: demo-$(date +%s)"
        echo "  • source_name: spotify"
        echo "  • status: completed"
        echo "  • risk_score: 62/100"
        echo ""
        echo "✅ Stockage réussi"
        """,
    )

    # Task 3: Simulation de mise à jour des métriques
    simulate_metrics = BashOperator(
        task_id="simulate_prometheus_metrics",
        bash_command="""
        echo "========================================="
        echo "📊 MISE À JOUR DES MÉTRIQUES PROMETHEUS"
        echo "========================================="
        echo ""
        echo "Métriques exposées:"
        echo "  • cgu_analyses_total: +1"
        echo "  • cgu_last_risk_score: 62"
        echo "  • cgu_data_privacy_score: 65"
        echo "  • cgu_termination_risk_score: 75"
        echo "  • cgu_legal_protection_score: 85"
        echo ""
        echo "✅ Métriques Prometheus mises à jour"
        echo "📈 Dashboard Grafana actualisé"
        """,
    )

    # Task 4: Rapport final
    final_report = BashOperator(
        task_id="generate_final_report",
        bash_command="""
        echo "========================================="
        echo "✅ PIPELINE TERMINÉ AVEC SUCCÈS"
        echo "========================================="
        echo ""
        echo "📋 RÉSUMÉ DE L'EXÉCUTION:"
        echo "  ✓ Analyse Claude AI: OK"
        echo "  ✓ Stockage MongoDB: OK"
        echo "  ✓ Métriques Prometheus: OK"
        echo "  ✓ Grafana Dashboard: OK"
        echo ""
        echo "🎯 RÉSULTAT FINAL:"
        echo "  Source: Spotify"
        echo "  Score: 62/100 (Préoccupant)"
        echo "  Clauses dangereuses: 4"
        echo ""
        echo "🔗 Consultez Grafana pour plus de détails"
        echo "========================================="
        """,
    )

    # Define dependencies
    simulate_analysis >> simulate_storage >> simulate_metrics >> final_report
