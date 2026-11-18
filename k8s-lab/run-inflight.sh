#!/bin/bash
set -e
kubectl --context kind-ozai-lab -n monitoring port-forward svc/prometheus-server 9090:80 >/dev/null 2>&1 &
PF=$!; trap "kill $PF" EXIT; sleep 30
python3 k8s-lab/loadtest.py benchmarks/04-k8s-lab/keda-inflight.json
