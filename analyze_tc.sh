#!/bin/bash
# 🚀 2Long2Read - T&C Analysis Script
# Usage: ./analyze_tc.sh <file.txt> [source_name]

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TASK_ID="analysis-$(date +%s)"
TC_FILE="$1"
SOURCE_NAME="${2:-direct_analysis}"

# Check arguments
if [ -z "$TC_FILE" ]; then
    echo -e "${YELLOW}Usage: ./analyze_tc.sh <file.txt> [source_name]${NC}"
    echo -e "${BLUE}Example: ./analyze_tc.sh raw_data/spotify_tc.txt spotify${NC}"
    exit 1
fi

if [ ! -f "$TC_FILE" ]; then
    echo -e "${YELLOW}Error: File not found: $TC_FILE${NC}"
    exit 1
fi

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}Warning: ANTHROPIC_API_KEY not set!${NC}"
    echo "Set it with: export ANTHROPIC_API_KEY='sk-ant-...'"
    exit 1
fi

echo -e "${GREEN}🚀 Starting T&C Analysis${NC}"
echo -e "${BLUE}Task ID: $TASK_ID${NC}"
echo -e "${BLUE}Source: $SOURCE_NAME${NC}"
echo -e "${BLUE}File: $TC_FILE${NC}"
echo ""

# Read content (limit to 40k chars)
CONTENT=$(head -c 40000 "$TC_FILE")
CHAR_COUNT=$(echo -n "$CONTENT" | wc -c | tr -d ' ')

echo -e "${GREEN}📄 Content loaded: $CHAR_COUNT characters${NC}"
echo ""

# Launch analysis pod
echo -e "${GREEN}🐳 Launching worker pod...${NC}"
kubectl run "tc-analysis-$TASK_ID" \
  --image=2long2read-worker:latest \
  --namespace=airflow \
  --restart=Never \
  --image-pull-policy=IfNotPresent \
  --env="MONGO_HOSTNAME=mongo-service.default.svc.cluster.local" \
  --env="MONGO_PORT=27017" \
  --env="ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
  -- --task-id "$TASK_ID" \
     --source-name "$SOURCE_NAME" \
     --text-content "$CONTENT"

echo ""
echo -e "${GREEN}📊 Analysis in progress...${NC}"

# Wait for pod to start and complete
echo -e "${BLUE}Waiting for pod to start...${NC}"

# Wait for pod to exist and start (max 30 seconds)
for i in {1..30}; do
    POD_STATUS=$(kubectl get pod "tc-analysis-$TASK_ID" --namespace=airflow -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
    if [ "$POD_STATUS" != "NotFound" ] && [ "$POD_STATUS" != "Pending" ]; then
        break
    fi
    sleep 1
done

echo -e "${BLUE}Pod started! Following logs...${NC}"
echo ""

# Follow logs until completion (with fallback)
kubectl logs -f "tc-analysis-$TASK_ID" --namespace=airflow 2>&1 || true

# Wait for pod to complete
echo ""
echo -e "${BLUE}Waiting for analysis to complete...${NC}"
kubectl wait --for=condition=Ready pod/"tc-analysis-$TASK_ID" --namespace=airflow --timeout=60s 2>/dev/null || \
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/"tc-analysis-$TASK_ID" --namespace=airflow --timeout=60s 2>/dev/null || true

# Get final logs if we missed any
kubectl logs "tc-analysis-$TASK_ID" --namespace=airflow 2>/dev/null | tail -10 || true

echo ""
echo -e "${GREEN}✅ Analysis complete!${NC}"
echo ""

# Wait a moment for MongoDB write
sleep 2

# Retrieve results
echo -e "${GREEN}📈 Results Summary:${NC}"
kubectl exec mongo-deployment-869dd489bf-bfwgx --namespace default -- \
  mongosh too_long_to_read --quiet --eval \
  "printjson(db.analytic_reports.findOne({\"task_id\": \"$TASK_ID\"}, {\"_id\": 0, \"task_id\": 1, \"status\": 1, \"report.risk_scores\": 1, \"report.executive_summary.overall_verdict\": 1}))"

echo ""
echo -e "${BLUE}Get full report:${NC}"
echo "kubectl exec mongo-deployment-869dd489bf-bfwgx --namespace default -- mongosh too_long_to_read --quiet --eval 'db.analytic_reports.findOne({\"task_id\": \"$TASK_ID\"})'"

echo ""
echo -e "${GREEN}🎉 Done! Task ID: $TASK_ID${NC}"
