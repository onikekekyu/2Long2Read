#!/bin/bash
set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     🎵 ANALYSE SPOTIFY TERMS & CONDITIONS                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
TASK_ID="spotify-$(date +%Y%m%d-%H%M%S)"
SOURCE_NAME="spotify"
SPOTIFY_FILE="${1:-raw_data/spotify_tc.txt}"
NAMESPACE="airflow"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"

echo "📋 Configuration:"
echo "   Task ID: $TASK_ID"
echo "   Source: $SOURCE_NAME"
echo "   File: $SPOTIFY_FILE"
echo "   Namespace: $NAMESPACE"
echo ""

# Vérifier que le fichier existe
if [ ! -f "$SPOTIFY_FILE" ]; then
    echo "❌ Erreur: Fichier $SPOTIFY_FILE introuvable"
    exit 1
fi

# Lire le contenu (limité à 10000 caractères pour l'API Claude)
CONTENT=$(head -c 10000 "$SPOTIFY_FILE" | base64 -w 0 2>/dev/null || head -c 10000 "$SPOTIFY_FILE" | base64)
CONTENT_SIZE=$(echo "$CONTENT" | wc -c)

echo "📄 Contenu chargé: $CONTENT_SIZE bytes (base64)"
echo ""

# Créer le manifest YAML du worker pod
POD_NAME="worker-$TASK_ID"
YAML_FILE="/tmp/${POD_NAME}.yaml"

cat > "$YAML_FILE" <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $POD_NAME
  namespace: $NAMESPACE
  labels:
    app: 2long2read-worker
    task-id: "$TASK_ID"
    source: "$SOURCE_NAME"
spec:
  restartPolicy: Never
  containers:
  - name: worker
    image: 2long2read-worker:latest
    imagePullPolicy: IfNotPresent
    command: ["sh", "-c"]
    args:
      - |
        echo "📥 Décodage du contenu base64..."
        echo "$CONTENT" | base64 -d > /tmp/content.txt
        echo "🚀 Lancement de l'analyse..."
        python3 /app/worker.py \\
          --task-id "$TASK_ID" \\
          --source-name "$SOURCE_NAME" \\
          --text-content "\$(cat /tmp/content.txt)"
    env:
      - name: MONGO_HOSTNAME
        value: "mongo-service.default.svc.cluster.local"
      - name: MONGO_PORT
        value: "27017"
      - name: ANTHROPIC_API_KEY
        value: "$ANTHROPIC_API_KEY"
      - name: CONTENT_BASE64
        value: "$CONTENT"
EOF

echo "📝 Manifest YAML créé: $YAML_FILE"
echo ""

# Créer le pod
echo "🚀 Création du worker pod..."
kubectl apply -f "$YAML_FILE"

echo "✅ Pod créé: $POD_NAME"
echo ""

# Attendre que le pod démarre
echo "⏳ Attente du démarrage du pod..."
kubectl wait --for=condition=Ready pod/$POD_NAME -n $NAMESPACE --timeout=60s || echo "⚠️ Timeout (normal si le pod termine rapidement)"
echo ""

# Suivre les logs
echo "📋 Logs du worker:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl logs -f $POD_NAME -n $NAMESPACE 2>/dev/null || kubectl logs $POD_NAME -n $NAMESPACE
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Attendre que le pod termine (max 5 minutes)
echo "⏳ Attente de la fin de l'analyse (max 5 min)..."
kubectl wait --for=condition=Completed pod/$POD_NAME -n $NAMESPACE --timeout=300s || true

# Vérifier le statut final
POD_STATUS=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
echo ""
echo "📊 Statut final du pod: $POD_STATUS"

if [ "$POD_STATUS" = "Succeeded" ] || [ "$POD_STATUS" = "Completed" ]; then
    echo "✅ Analyse terminée avec succès!"
    echo ""
    echo "🔍 Vérification dans MongoDB..."

    # Récupérer les résultats de MongoDB
    MONGO_POD=$(kubectl get pods -n default -l app=mongo -o jsonpath='{.items[0].metadata.name}')
    kubectl exec $MONGO_POD -n default -- \
        mongosh too_long_to_read --quiet --eval \
        "db.analytic_reports.findOne({\"task_id\": \"$TASK_ID\"}, {\"_id\": 0, \"task_id\": 1, \"status\": 1, \"report.risk_scores\": 1})" \
        | head -20

    echo ""
    echo "💾 Task ID pour consultation: $TASK_ID"
    echo "📊 Métriques Prometheus disponibles sur: http://api-service:8000/metrics"

    exit 0
else
    echo "❌ Analyse échouée avec le statut: $POD_STATUS"
    echo ""
    echo "📋 Derniers logs:"
    kubectl logs $POD_NAME -n $NAMESPACE --tail=50
    exit 1
fi
