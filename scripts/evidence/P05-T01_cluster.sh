#!/usr/bin/env bash
# P05-T01 · the cluster exists with Calico, metrics-server and ingress · K8-22
set -euo pipefail
OUT=docs/evidence/cluster_up.txt
mkdir -p "$(dirname "$OUT")"
{
  echo "# P05-T01 captured $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# requirement: K8-22 (metrics-server), and Calico so NetworkPolicy is enforced"
  echo; echo "\$ minikube version";        minikube version 2>&1
  echo; echo "\$ kubectl get nodes -o wide"; kubectl get nodes -o wide 2>&1
  echo; echo "\$ minikube addons list | grep -E 'metrics-server|ingress'"
  minikube addons list 2>&1 | grep -E 'metrics-server|ingress'
  echo; echo "\$ kubectl get pods -n kube-system -l k8s-app=calico-node"
  kubectl get pods -n kube-system 2>&1 | grep -i calico || echo "NO CALICO - NetworkPolicy will be silently ignored"
  echo; echo "\$ kubectl get pods -n ingress-nginx"
  kubectl get pods -n ingress-nginx 2>&1
  echo; echo "\$ minikube ip"; minikube ip 2>&1
  echo; echo "\$ minikube ssh \"grep host.minikube.internal /etc/hosts\""
  minikube ssh "grep host.minikube.internal /etc/hosts" 2>&1
  echo "# ^ put that IP into k8s/overlays/dev/patch-host-ipblock.yaml"
} | tee "$OUT"
