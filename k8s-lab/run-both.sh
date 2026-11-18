#!/bin/bash
# Baseline (autoscaling paused at 1 replica) then KEDA run, same load profile.
set -e
K="kubectl --context kind-ozai-lab -n ozai"
kubectl --context kind-ozai-lab -n monitoring port-forward svc/prometheus-server 9090:80 >/dev/null 2>&1 &
PF=$!; trap "kill $PF" EXIT; sleep 3
$K annotate scaledobject ozai-lab autoscaling.keda.sh/paused-replicas="1" --overwrite
sleep 20
python3 k8s-lab/loadtest.py benchmarks/04-k8s-lab/baseline-1-replica.json
$K annotate scaledobject ozai-lab autoscaling.keda.sh/paused-replicas-
echo "waiting for steady state"; sleep 90
python3 k8s-lab/loadtest.py benchmarks/04-k8s-lab/keda.json
