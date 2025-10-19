#!/bin/bash
# Script pour accéder à Grafana
# Usage: ./access_grafana.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}📊 Accès à Grafana${NC}"
echo ""
echo -e "${BLUE}Identifiants Grafana:${NC}"
echo "  Username: admin"
echo "  Password: prom-operator"
echo ""
echo -e "${GREEN}Démarrage du port-forward...${NC}"
echo -e "${BLUE}URL: http://localhost:3000${NC}"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter"
echo ""

# Lancer le port-forward
kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80
