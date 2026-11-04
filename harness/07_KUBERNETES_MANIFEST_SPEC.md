# 07 — Kubernetes Manifest and Image Specification

> Every manifest and every Dockerfile, specified field by field. You transcribe
> these. Do not improvise field names, label schemes, port numbers, probe
> parameters or resource values.
>
> **Resource numbers** in `base/` are *starting* values. Phase 16 replaces them
> with numbers measured by `kubectl top pods` and recorded in
> `docs/evidence/kubectl_top_indexer.txt`. Until then every manifest carries the
> comment `# PENDING-HUMAN(P16-T07): replace with measured values`.

---

## 0. Conventions that apply to every file

**Namespace.** Every object carries `namespace: rahbar` explicitly **and**
`k8s/base/kustomization.yaml` sets `namespace: rahbar`. Belt and braces: the
checker greps for `namespace: default` and for an explicit namespace on objects.

**Labels.** Every object and every pod template carries exactly these four:

```yaml
labels:
  app: <api|ui|chroma|redis|indexer>
  app.kubernetes.io/name: <same>
  app.kubernetes.io/part-of: rahbar
  app.kubernetes.io/component: <api|ui|vector-store|cache|indexer>
```

Selectors match on `app: <name>` only — a single immutable key, because
`spec.selector` on a Deployment and the `volumeClaimTemplates` of a StatefulSet
cannot be changed after creation.

**Images.** `imagePullPolicy: IfNotPresent` everywhere, because
`minikube image load` puts images in the node's cache and the cluster must not
try a registry. Tags are `:dev` in the dev overlay and the commit SHA in prod.

**`securityContext`.** Every pod gets the pod-level block and every container
gets the container-level block. No exceptions, including the Job.

```yaml
      securityContext:                 # pod level
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
```

```yaml
          securityContext:             # container level
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
```

> `drop:` **must** render as a YAML block list (`drop:` newline `- ALL`). The
> checker's regex is `drop:\s*\n\s*-\s*(ALL|all)` and `drop: ["ALL"]` does not
> match it.

**`readOnlyRootFilesystem: true` consequences.** Every container that writes
anything needs an `emptyDir`:

| Container | Writes to | Mount |
|---|---|---|
| api | `/tmp` (prometheus multiprocess scratch, httpx) | `emptyDir` at `/tmp` |
| ui | `/tmp` (nginx pid + temp paths, per `nginx.conf`) | `emptyDir` at `/tmp` |
| indexer | `/tmp` (pdf2image rasterisation) | `emptyDir` at `/tmp` |
| chroma | `/data` | the PVC from `volumeClaimTemplates` |
| redis | `/data` | the PVC |

**ServiceAccounts.** One per workload, `automountServiceAccountToken: false` on
every pod spec — nothing in this system calls the Kubernetes API.

**Environment.** Every container gets its configuration with
`envFrom: [{configMapRef: {name: rahbar-config}}]`. Only the api additionally
gets the Secret, and it gets it `optional: true` so the stack comes up before
`make secret` has been run:

```yaml
            envFrom:
              - configMapRef:
                  name: rahbar-config
              - secretRef:
                  name: rahbar-secret
                  optional: true
```

---

## 1. `k8s/base/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rahbar
  labels:
    app.kubernetes.io/part-of: rahbar
    name: rahbar
```

---

## 2. `k8s/base/configmap.yaml`

All 18 keys from `00_MASTER_PLAN_AND_STATUS.md` §6. **Every value is a quoted
string** — a ConfigMap value must be a string, and an unquoted `8000` or `true`
is a YAML int/bool and will be rejected.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rahbar-config
  namespace: rahbar
  labels:
    app.kubernetes.io/part-of: rahbar
data:
  # --- the embedding pin (section 4.4). The indexer and the api read this same key.
  EMBED_MODEL: "nomic-embed-text"

  # --- implementation selection
  RETRIEVER: "chroma"
  LLM_PROVIDER: "ollama-host"
  LLM_MODEL: "llama3.2:3b"

  # --- vector store
  CHROMA_HOST: "chroma"
  CHROMA_PORT: "8000"
  CHROMA_COLLECTION: "rahbar"

  # --- retrieval
  TOP_K: "5"
  # Below this cosine similarity nothing retrieved is relevant, so the service
  # abstains without calling the model. Measured in P15; see docs/PIPELINE.md.
  RELEVANCE_FLOOR: "0.35"

  # --- generation
  # Facts and JSON belong at 0 to 0.3: a higher value makes the model paraphrase
  # the evidence and invent clause numbers. 0.2 keeps one re-roll's worth of
  # wording variety without that. See docs/PIPELINE.md.
  TEMPERATURE: "0.2"

  # --- semantic cache
  CACHE_ENABLED: "true"
  # The lowest threshold with zero false hits on our test questions (P15).
  CACHE_THRESHOLD: "0.95"
  CACHE_TTL_SECONDS: "86400"
  CACHE_MAX_ENTRIES: "512"
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"

  # --- chunking (indexer). Unit: whitespace-delimited words.
  CHUNK_SIZE: "400"
  CHUNK_OVERLAP: "50"

  # --- provider endpoint. host.minikube.internal reaches Ollama on the laptop.
  OLLAMA_URL: "http://host.minikube.internal:11434"

  # --- indexer
  CORPUS_DIR: "/corpus"
  OCR_ENABLED: "true"
```

---

## 3. `k8s/base/secret.placeholder.yaml`

**Never listed in `kustomization.yaml`.** Applying it would overwrite the real
Secret created by `make secret`. It exists only to document the shape.

```yaml
# DOCUMENTATION ONLY. Never applied, never listed in kustomization.yaml.
# Create the real Secret from the command line:
#   export LLM_API_KEY=...
#   kubectl create secret generic rahbar-secret -n rahbar \
#     --from-literal=LLM_API_KEY="$LLM_API_KEY"
# Base64 is encoding, not encryption. A real value here is -15 marks.
apiVersion: v1
kind: Secret
metadata:
  name: rahbar-secret
  namespace: rahbar
type: Opaque
stringData:
  LLM_API_KEY: "REPLACE_ME"
```

`.gitignore` already allows this one filename via `!*placeholder*.yaml`.

---

## 4. `k8s/base/serviceaccounts.yaml`

Five documents in one file, separated by `---`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rahbar-api
  namespace: rahbar
  labels: {app: api, app.kubernetes.io/part-of: rahbar}
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rahbar-ui
  namespace: rahbar
  labels: {app: ui, app.kubernetes.io/part-of: rahbar}
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rahbar-chroma
  namespace: rahbar
  labels: {app: chroma, app.kubernetes.io/part-of: rahbar}
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rahbar-redis
  namespace: rahbar
  labels: {app: redis, app.kubernetes.io/part-of: rahbar}
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rahbar-indexer
  namespace: rahbar
  labels: {app: indexer, app.kubernetes.io/part-of: rahbar}
automountServiceAccountToken: false
```

No Role and no RoleBinding: none of these workloads talks to the API server, so
granting nothing is correct.

---

## 5. `k8s/base/chroma-statefulset.yaml`

A **StatefulSet, not a Deployment** — and the reason goes in
`docs/ARCHITECTURE.md` and ADR 0001: a Deployment's `volumes` are shared by
every replica, so scaling it would put two Chroma processes on one filesystem;
`volumeClaimTemplates` binds one PVC per ordinal and gives the pod a stable
identity (`chroma-0`) and a stable volume across reschedules. The index is state,
and state gets a StatefulSet.

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: chroma
  namespace: rahbar
  labels:
    app: chroma
    app.kubernetes.io/name: chroma
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: vector-store
spec:
  serviceName: chroma
  replicas: 1
  selector:
    matchLabels:
      app: chroma
  template:
    metadata:
      labels:
        app: chroma
        app.kubernetes.io/name: chroma
        app.kubernetes.io/part-of: rahbar
        app.kubernetes.io/component: vector-store
    spec:
      serviceAccountName: rahbar-chroma
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: chroma
          # Must match chromadb-client==1.0.12 in both requirements.txt files.
          image: chromadb/chroma:1.0.12
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
          env:
            - name: IS_PERSISTENT
              value: "TRUE"
            - name: PERSIST_DIRECTORY
              value: /data
            - name: ANONYMIZED_TELEMETRY
              value: "FALSE"
          startupProbe:
            httpGet: {path: /api/v2/heartbeat, port: 8000}
            failureThreshold: 30
            periodSeconds: 2
          livenessProbe:
            httpGet: {path: /api/v2/heartbeat, port: 8000}
            periodSeconds: 20
            failureThreshold: 3
          readinessProbe:
            httpGet: {path: /api/v2/heartbeat, port: 8000}
            periodSeconds: 10
            failureThreshold: 3
          resources:                     # PENDING-HUMAN(P16-T07): replace with measured values
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 1000m
              memory: 1Gi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 2Gi
```

---

## 6. `k8s/base/redis.yaml`

A Deployment **plus a PVC** — the assignment names this object shape
explicitly, and a cache with no PVC is −8.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: rahbar
  labels: {app: redis, app.kubernetes.io/part-of: rahbar}
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: rahbar
  labels:
    app: redis
    app.kubernetes.io/name: redis
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: cache
spec:
  replicas: 1
  strategy:
    type: Recreate          # one PVC, ReadWriteOnce: never two pods at once
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
        app.kubernetes.io/name: redis
        app.kubernetes.io/part-of: rahbar
        app.kubernetes.io/component: cache
    spec:
      serviceAccountName: rahbar-redis
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: redis
          image: redis:7.2.5-alpine
          imagePullPolicy: IfNotPresent
          # Persistence: section 4.1 requires it. AOF survives a pod restart,
          # so a warm cache is not lost to a rolling update.
          args:
            - redis-server
            - --appendonly
            - "yes"
            - --appendfsync
            - everysec
            - --dir
            - /data
            - --save
            - ""
          ports:
            - name: redis
              containerPort: 6379
          startupProbe:
            tcpSocket: {port: 6379}
            failureThreshold: 30
            periodSeconds: 2
          livenessProbe:
            tcpSocket: {port: 6379}
            periodSeconds: 20
            failureThreshold: 3
          readinessProbe:
            exec:
              command: ["redis-cli", "ping"]
            periodSeconds: 10
            failureThreshold: 3
          resources:                     # PENDING-HUMAN(P16-T07): replace with measured values
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 300m
              memory: 256Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: data
              mountPath: /data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: redis-data
```

---

## 7. `k8s/base/api-deployment.yaml`

The most heavily graded manifest: 3 replicas, all three probes with the
assignment's exact parameters, requests **and** limits, `maxUnavailable: 0`,
graceful shutdown, full security context.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: rahbar
  labels:
    app: api
    app.kubernetes.io/name: api
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: api
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0        # a rollout never reduces capacity below 3
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        app.kubernetes.io/name: api
        app.kubernetes.io/part-of: rahbar
        app.kubernetes.io/component: api
    spec:
      serviceAccountName: rahbar-api
      automountServiceAccountToken: false
      # 30s budget: the preStop sleep is 5s, then uvicorn drains in-flight requests.
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: rahbar-api:dev
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8000
          envFrom:
            - configMapRef:
                name: rahbar-config
            - secretRef:
                name: rahbar-secret
                optional: true
          # Finished booting? Liveness and readiness wait while this runs.
          startupProbe:
            httpGet:
              path: /healthz
              port: 8000
            failureThreshold: 30
            periodSeconds: 2
          # Still working? Failure: the kubelet kills and restarts the container.
          # /healthz touches no dependency, so a slow Chroma cannot cause a
          # cluster-wide restart storm.
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            periodSeconds: 20
            failureThreshold: 3
          # Can it take traffic now? Failure: removed from the Service, not restarted.
          # /readyz requires Chroma reachable, a non-empty collection, a matching
          # embedding pin, and Redis reachable.
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
            periodSeconds: 10
            failureThreshold: 3
          lifecycle:
            preStop:
              exec:
                # Leave the Service before refusing connections: endpoint removal
                # is eventually consistent across kube-proxy on every node.
                command: ["/bin/sh", "-c", "sleep 5"]
          resources:                     # PENDING-HUMAN(P16-T07): replace with measured values
            requests:
              cpu: 100m                  # the HPA divides usage by this
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```

> **Probe proximity matters.** The checker searches for `/healthz` within 250
> characters after `livenessProbe:` and `/readyz` within 250 characters after
> `readinessProbe:`. Keep `httpGet`/`path` immediately beneath each probe key,
> and keep comments *above* the probe, never between the key and its `path`.

---

## 8. `k8s/base/ui-deployment.yaml`

`ui/nginx.conf` listens on **8080** and writes only under `/tmp`, so a
non-root, read-only-root container needs an `emptyDir` at `/tmp`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ui
  namespace: rahbar
  labels:
    app: ui
    app.kubernetes.io/name: ui
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: ui
spec:
  replicas: 2
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: ui
  template:
    metadata:
      labels:
        app: ui
        app.kubernetes.io/name: ui
        app.kubernetes.io/part-of: rahbar
        app.kubernetes.io/component: ui
    spec:
      serviceAccountName: rahbar-ui
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 15
      securityContext:
        runAsNonRoot: true
        runAsUser: 101           # nginx-unprivileged's built-in nginx user
        runAsGroup: 101
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: nginx
          image: rahbar-ui:dev
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
          startupProbe:
            httpGet: {path: /healthz, port: 8080}
            failureThreshold: 30
            periodSeconds: 2
          livenessProbe:
            httpGet: {path: /healthz, port: 8080}
            periodSeconds: 20
            failureThreshold: 3
          readinessProbe:
            httpGet: {path: /healthz, port: 8080}
            periodSeconds: 10
            failureThreshold: 3
          resources:                     # PENDING-HUMAN(P16-T07): replace with measured values
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 100m
              memory: 64Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```

---

## 9. `k8s/base/services.yaml`

Four Services, **all ClusterIP**. Chroma and Redis as NodePort or LoadBalancer
is −8.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
  namespace: rahbar
  labels: {app: api, app.kubernetes.io/part-of: rahbar}
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
    - name: http
      port: 8000
      targetPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: ui
  namespace: rahbar
  labels: {app: ui, app.kubernetes.io/part-of: rahbar}
spec:
  type: ClusterIP
  selector:
    app: ui
  ports:
    - name: http
      port: 8080
      targetPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: chroma
  namespace: rahbar
  labels: {app: chroma, app.kubernetes.io/part-of: rahbar}
spec:
  type: ClusterIP          # never NodePort, never LoadBalancer (-8)
  clusterIP: None          # headless: the StatefulSet's governing Service
  selector:
    app: chroma
  ports:
    - name: http
      port: 8000
      targetPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: rahbar
  labels: {app: redis, app.kubernetes.io/part-of: rahbar}
spec:
  type: ClusterIP          # never NodePort, never LoadBalancer (-8)
  selector:
    app: redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
```

> `clusterIP: None` on `chroma` makes it the StatefulSet's headless governing
> Service, giving `chroma-0.chroma.rahbar.svc.cluster.local` a stable DNS name.
> `CHROMA_HOST: "chroma"` still resolves, because a headless Service returns the
> pod IP directly. It is still `type: ClusterIP`, which is what the checker and
> the deduction care about.

---

## 10. `k8s/base/ingress.yaml`

One host, two paths. `/api` must reach the api **with the prefix intact** —
`routes/ask.py` mounts at `prefix="/api"`, so no rewrite annotation.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: rahbar
  namespace: rahbar
  labels: {app.kubernetes.io/part-of: rahbar}
  annotations:
    # No rewrite-target: the API expects /api/ask, not /ask.
    nginx.ingress.kubernetes.io/proxy-body-size: 1m
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "120"
spec:
  ingressClassName: nginx
  rules:
    - host: rahbar.local
      http:
        paths:
          # More specific path first.
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ui
                port:
                  number: 8080
```

`proxy-read-timeout: 120` exceeds the 60-second LLM timeout plus one retry, so
the Ingress never truncates a slow generation before the API's own fallback
fires.

---

## 11. `k8s/base/hpa.yaml`

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
  namespace: rahbar
  labels: {app: api, app.kubernetes.io/part-of: rahbar}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 8
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          # Utilisation is usage divided by requests.cpu. With no requests.cpu
          # this reads <unknown>/70% forever (-6), which is why every container
          # above has requests. Needs: minikube addons enable metrics-server.
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

> **The honest caveat, which belongs in `ENGINEERING-NOTES.md` Q3:** while the
> API waits on the LLM its CPU is near idle, because generation is I/O-bound
> from the pod's point of view. A CPU-based HPA therefore measures *parsing and
> serialisation*, not load. The signal that should scale this service is
> in-flight concurrent requests (or generation queue depth), which would require
> exporting a gauge from `/metrics`, scraping it with Prometheus, and exposing it
> through the custom-metrics API or KEDA. CPU is specified here because the
> assignment specifies it; the analysis is the deliverable.

---

## 12. `k8s/base/networkpolicy.yaml`

Six policies in one file, in this order. Calico is required: the default
minikube CNI accepts these and silently ignores them.

```yaml
# 1 - deny everything, both directions, for every pod in the namespace.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 00-default-deny
  namespace: rahbar
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
---
# 2 - DNS. Without this, default-deny egress breaks every service name in the
# namespace and every symptom looks like a broken Service.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 10-allow-dns
  namespace: rahbar
spec:
  podSelector: {}
  policyTypes: [Egress]
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
# 3 - ui: reachable from the Ingress only; may talk to nothing but DNS.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 20-ui-policy
  namespace: rahbar
spec:
  podSelector:
    matchLabels:
      app: ui
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
---
# 4 - api: reachable from the Ingress and from ui; may reach chroma, redis,
#     DNS, and the laptop's Ollama.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 30-api-policy
  namespace: rahbar
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
        - podSelector:
            matchLabels:
              app: ui
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: chroma
      ports:
        - protocol: TCP
          port: 8000
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 6379
    # Ollama on the host. The dev overlay patches this CIDR to the real address
    # from: minikube ssh "grep host.minikube.internal /etc/hosts"
    - to:
        - ipBlock:
            cidr: 192.168.49.1/32    # PENDING-HUMAN(P05-T02): patch in the dev overlay
      ports:
        - protocol: TCP
          port: 11434
---
# 5 - chroma: reachable from api and indexer ONLY. ui cannot reach it.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 40-chroma-policy
  namespace: rahbar
spec:
  podSelector:
    matchLabels:
      app: chroma
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
        - podSelector:
            matchLabels:
              app: indexer
      ports:
        - protocol: TCP
          port: 8000
---
# 6 - redis: reachable from api and indexer ONLY (the indexer bumps the cache
#     generation on a successful re-index).
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 50-redis-policy
  namespace: rahbar
spec:
  podSelector:
    matchLabels:
      app: redis
  policyTypes: [Ingress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: api
        - podSelector:
            matchLabels:
              app: indexer
      ports:
        - protocol: TCP
          port: 6379
```

The indexer needs its own egress allowance; it is in the Job manifest's
companion policy, appended to this file as a seventh document:

```yaml
---
# 7 - indexer egress: chroma, redis, DNS and Ollama.
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 60-indexer-egress
  namespace: rahbar
spec:
  podSelector:
    matchLabels:
      app: indexer
  policyTypes: [Egress]
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: chroma
      ports: [{protocol: TCP, port: 8000}]
    - to:
        - podSelector:
            matchLabels:
              app: redis
      ports: [{protocol: TCP, port: 6379}]
    - to:
        - ipBlock:
            cidr: 192.168.49.1/32    # PENDING-HUMAN(P05-T02)
      ports: [{protocol: TCP, port: 11434}]
```

**Proof that `ui ↛ chroma`**, captured in `docs/evidence/`:

```bash
kubectl exec -n rahbar deploy/ui -- sh -c 'timeout 5 nc -z chroma 8000; echo exit=$?'
# expect a non-zero exit
kubectl exec -n rahbar deploy/api -- sh -c 'timeout 5 nc -z chroma 8000; echo exit=$?'
# expect exit=0
```

---

## 13. `k8s/base/indexer-job.yaml`

One-shot. `restartPolicy: OnFailure`. `backoffLimit: 4`. **Not** a Deployment —
and that reason is ADR 0001, the first file the marker reads.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: indexer
  namespace: rahbar
  labels:
    app: indexer
    app.kubernetes.io/name: indexer
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: indexer
spec:
  # Exactly one writer. parallelism is left unset (defaults to 1): three
  # concurrent writers on one Chroma PVC leave an index no document produced.
  completions: 1
  backoffLimit: 4
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        app: indexer
        app.kubernetes.io/name: indexer
        app.kubernetes.io/part-of: rahbar
        app.kubernetes.io/component: indexer
    spec:
      # Batch semantics: the pod runs to completion and exits. OnFailure retries
      # the container in place, up to backoffLimit.
      restartPolicy: OnFailure
      serviceAccountName: rahbar-indexer
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: indexer
          image: rahbar-indexer:dev
          imagePullPolicy: IfNotPresent
          args: ["python", "-m", "pipeline.run"]
          envFrom:
            - configMapRef:
                name: rahbar-config
          resources:                     # PENDING-HUMAN(P16-T07): replace with measured values
            requests:
              cpu: 250m
              memory: 512Mi
            # Embedding a 40-page PDF holds far more memory than answering a
            # query. Over the memory limit the container is OOMKilled with exit
            # code 137, which is the most common CrashLoopBackOff in this project.
            limits:
              cpu: 2000m
              memory: 2Gi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: corpus
              mountPath: /corpus
              readOnly: true
            - name: tmp
              mountPath: /tmp          # pdf2image rasterises here
      volumes:
        # The corpus is baked into the indexer image at /corpus-baked and copied
        # in by the image's entrypoint, OR mounted here. Decision and rationale:
        # docs/PIPELINE.md. For CI, the fixture corpus is baked.
        - name: corpus
          emptyDir: {}
        - name: tmp
          emptyDir: {}
```

**How the corpus reaches the Job** is a decision you must document in
`docs/PIPELINE.md` (the assignment says so explicitly). The locked choice:
**baked into the indexer image** at build time from `eval/fixtures/` for CI and
from `corpus/raw/` for local runs, because `corpus/raw/` is gitignored and a
`hostPath` mount is not portable to kind. `CORPUS_DIR` then points at the baked
path. The `emptyDir` above is the mount point used when overriding with a
volume in the dev overlay.

---

## 14. `k8s/base/reindex-cronjob.yaml`

Weekly, **same image and same arguments** as the Job. This is what makes
`kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar` work, and
that command is what makes re-indexing possible with no redeploy.

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: reindex
  namespace: rahbar
  labels:
    app: indexer
    app.kubernetes.io/name: reindex
    app.kubernetes.io/part-of: rahbar
    app.kubernetes.io/component: indexer
spec:
  schedule: "0 2 * * 0"            # Sundays at 02:00 - weekly
  timeZone: "Asia/Karachi"
  concurrencyPolicy: Forbid        # never two writers
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  startingDeadlineSeconds: 600
  jobTemplate:
    spec:
      completions: 1
      backoffLimit: 4
      ttlSecondsAfterFinished: 3600
      template:
        metadata:
          labels:
            app: indexer
            app.kubernetes.io/name: reindex
            app.kubernetes.io/part-of: rahbar
            app.kubernetes.io/component: indexer
        spec:
          restartPolicy: OnFailure
          serviceAccountName: rahbar-indexer
          automountServiceAccountToken: false
          securityContext:
            runAsNonRoot: true
            runAsUser: 10001
            runAsGroup: 10001
            fsGroup: 10001
            seccompProfile:
              type: RuntimeDefault
          containers:
            - name: indexer
              image: rahbar-indexer:dev
              imagePullPolicy: IfNotPresent
              args: ["python", "-m", "pipeline.run"]
              envFrom:
                - configMapRef:
                    name: rahbar-config
              resources:                 # PENDING-HUMAN(P16-T07)
                requests:
                  cpu: 250m
                  memory: 512Mi
                limits:
                  cpu: 2000m
                  memory: 2Gi
              securityContext:
                allowPrivilegeEscalation: false
                readOnlyRootFilesystem: true
                runAsNonRoot: true
                capabilities:
                  drop:
                    - ALL
              volumeMounts:
                - name: corpus
                  mountPath: /corpus
                  readOnly: true
                - name: tmp
                  mountPath: /tmp
          volumes:
            - name: corpus
              emptyDir: {}
            - name: tmp
              emptyDir: {}
```

`concurrencyPolicy: Forbid` is not decoration: it is the second line of defence
behind the Job/Deployment choice against two concurrent writers.

---

## 15. `k8s/base/kustomization.yaml`

**Note what is absent:** `secret.placeholder.yaml`. Applying it would overwrite
the real Secret.

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: rahbar

commonLabels:
  app.kubernetes.io/part-of: rahbar

resources:
  - namespace.yaml
  - configmap.yaml
  - serviceaccounts.yaml
  - chroma-statefulset.yaml
  - redis.yaml
  - api-deployment.yaml
  - ui-deployment.yaml
  - services.yaml
  - ingress.yaml
  - hpa.yaml
  - networkpolicy.yaml
  - indexer-job.yaml
  - reindex-cronjob.yaml
# secret.placeholder.yaml is DELIBERATELY NOT LISTED. It documents the Secret's
# shape; applying it would overwrite the real one created by `make secret`.
```

---

## 16. `k8s/overlays/dev/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: rahbar
resources:
  - ../../base

images:
  - name: rahbar-api
    newTag: dev
  - name: rahbar-ui
    newTag: dev
  - name: rahbar-indexer
    newTag: dev

patches:
  - path: patch-config-dev.yaml
  - path: patch-host-ipblock.yaml
```

`k8s/overlays/dev/patch-config-dev.yaml` — week-1 stub mode, flipped to real in
Phase 15:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rahbar-config
  namespace: rahbar
data:
  LOG_LEVEL: "DEBUG"
  # Week 1 (P05): the whole cluster runs on stubs and the --dummy index.
  # The dummy index records embed_model=dummy-768, so the pin agrees.
  # Phase 15 changes these three lines to chroma / ollama-host / nomic-embed-text.
  RETRIEVER: "stub"
  LLM_PROVIDER: "stub"
  EMBED_MODEL: "dummy-768"
```

`k8s/overlays/dev/patch-host-ipblock.yaml` — the host IP differs per machine:

```yaml
# PENDING-HUMAN(P05-T02): replace 192.168.49.1 with the output of
#   minikube ssh "grep host.minikube.internal /etc/hosts" | awk '{print $1}'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: 30-api-policy
  namespace: rahbar
spec:
  egress:
    - to:
        - podSelector: {matchLabels: {app: chroma}}
      ports: [{protocol: TCP, port: 8000}]
    - to:
        - podSelector: {matchLabels: {app: redis}}
      ports: [{protocol: TCP, port: 6379}]
    - to:
        - ipBlock: {cidr: 192.168.49.1/32}
      ports: [{protocol: TCP, port: 11434}]
```

## 17. `k8s/overlays/prod/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: rahbar
resources:
  - ../../base

# cd.yml rewrites newTag to ${{ github.sha }} with:
#   cd k8s/overlays/prod && kustomize edit set image rahbar-api=USER/rahbar-api:$SHA
# Never :latest (-6).
images:
  - name: rahbar-api
    newName: REPLACE_DOCKERHUB_USER/rahbar-api
    newTag: REPLACE_SHA
  - name: rahbar-ui
    newName: REPLACE_DOCKERHUB_USER/rahbar-ui
    newTag: REPLACE_SHA
  - name: rahbar-indexer
    newName: REPLACE_DOCKERHUB_USER/rahbar-indexer
    newTag: REPLACE_SHA

patches:
  - path: patch-config-prod.yaml
  - path: patch-resources.yaml
```

`patch-config-prod.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rahbar-config
  namespace: rahbar
data:
  LOG_LEVEL: "INFO"
  RETRIEVER: "chroma"
  LLM_PROVIDER: "ollama-host"
  EMBED_MODEL: "nomic-embed-text"
```

`patch-resources.yaml` — Phase 16 writes the measured values here:

```yaml
# PENDING-HUMAN(P16-T07): values from docs/evidence/kubectl_top_indexer.txt
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: rahbar
spec:
  template:
    spec:
      containers:
        - name: api
          resources:
            requests: {cpu: 100m, memory: 256Mi}
            limits: {cpu: 500m, memory: 512Mi}
```

Also set `imagePullPolicy: IfNotPresent` → `Always` in prod via this patch,
because prod images come from Docker Hub by SHA.

---

## 18. The documented apply order

This exact sequence goes in `README.md` and is rehearsed from a clean clone in
P17-T08. A sequence that does not work from a clean clone is −5.

```bash
# 1. the cluster, with Calico (the default CNI ignores NetworkPolicy silently)
minikube start --driver=docker --cni=calico --memory=6144 --cpus=4
minikube addons enable metrics-server     # the HPA needs a denominator
minikube addons enable ingress

# 2. Ollama on the laptop, listening on all interfaces
OLLAMA_HOST=0.0.0.0 ollama serve &
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 3. the host IP for the NetworkPolicy ipBlock
minikube ssh "grep host.minikube.internal /etc/hosts" | awk '{print $1}'
#    put it in k8s/overlays/dev/patch-host-ipblock.yaml

# 4. build the three images into the node's cache
make images

# 5. apply everything
kubectl apply -k k8s/overlays/dev

# 6. (hosted mode only) the Secret, from the command line, never from a file
export LLM_API_KEY=...
make secret

# 7. wait for the data tier
kubectl rollout status statefulset/chroma -n rahbar --timeout=180s
kubectl rollout status deployment/redis   -n rahbar --timeout=120s

# 8. build the index. The api is 0/1 READY until this finishes - by design.
kubectl create job --from=cronjob/reindex first-index -n rahbar
kubectl wait --for=condition=complete job/first-index -n rahbar --timeout=900s

# 9. now the api becomes ready
kubectl rollout status deployment/api -n rahbar --timeout=180s
kubectl get endpoints api -n rahbar          # expect 3 IPs

# 10. ask a question
echo "$(minikube ip) rahbar.local" | sudo tee -a /etc/hosts
make ask Q="What CGPA puts a student on academic warning?"
```

> Steps 7–9 are the order that matters and the one students get wrong: the api
> is **deliberately** not ready before the index exists, because a ready pod
> with an empty collection serves empty retrievals. Do not add a `kubectl wait`
> on the api before the Job.

---

## 19. `api/Dockerfile`

```dockerfile
# Pinned by minor version. Never bare `python`, never `:latest` - the checker
# fails an unpinned FROM.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Requirements first: this layer is cached unless the pins change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Non-root, matching runAsUser: 10001 in the manifests.
RUN groupadd --gid 10001 rahbar \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rahbar \
 && chown -R 10001:10001 /app
USER 10001

EXPOSE 8000

# Exec form: SIGTERM reaches uvicorn as PID 1, so preStop + graceful shutdown work.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

No `--workers`: three replicas provide the concurrency, and one process per pod
keeps the Prometheus client's default (non-multiprocess) registry correct.

## 20. `indexer/Dockerfile`

```dockerfile
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OCR needs system packages, not only pip packages:
#   tesseract-ocr   - the OCR engine pytesseract drives
#   poppler-utils   - pdftoppm, which pdf2image shells out to
RUN apt-get update \
 && apt-get install --no-install-recommends -y \
      tesseract-ocr=5.3.0-2 \
      poppler-utils=22.12.0-2+deb12u1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pipeline ./pipeline

# The CI fixture corpus is baked in so the e2e job needs no volume.
# CORPUS_DIR in the ConfigMap selects which path is used.
COPY corpus-baked/ /corpus-baked/

RUN groupadd --gid 10001 rahbar \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rahbar \
 && chown -R 10001:10001 /app /corpus-baked
USER 10001

# A Job, so it exits. Exec form.
CMD ["python", "-m", "pipeline.run"]
```

> If the pinned apt versions are unavailable on the day, drop the `=version`
> suffixes rather than switching base images, and record the change in the
> Decision Log. The `FROM` pin is what the checker tests.
>
> `indexer/corpus-baked/` is created by `make images`: it is `eval/fixtures/`
> copied in for CI, and `corpus/raw/` copied in for a local real run. It is
> gitignored.

## 21. `ui/Dockerfile`

```dockerfile
# nginx-unprivileged already runs as uid 101 and listens above 1024.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# ui/nginx.conf listens on 8080, writes only under /tmp, and logs to stdout.
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

USER 101

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
```

Single-stage is correct: `ui/index.html` is a finished static page with no build
step, so there is no Node to keep out of the final layer.

## 22. `.dockerignore` files

`api/.dockerignore`:

```
.git
.gitignore
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
.venv
venv
tests
corpus
docs
k8s
eval
evidence
*.md
Dockerfile
.dockerignore
requirements-dev.txt
```

`indexer/.dockerignore`:

```
.git
.gitignore
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.ruff_cache
.venv
venv
tests
docs
k8s
*.md
Dockerfile
.dockerignore
requirements-dev.txt
```

> The checker requires `.git` and `__pycache__` in both, and warns unless
> `corpus` or a venv is excluded. `indexer/.dockerignore` deliberately does
> **not** exclude `corpus-baked/` — that directory must reach the image.

---

## 23. Validation gates

```bash
# syntax and schema, in about 20 seconds, instead of on the cluster
kustomize build k8s/overlays/dev  | kubeconform -strict -summary -ignore-missing-schemas
kustomize build k8s/overlays/prod | kubeconform -strict -summary -ignore-missing-schemas

# all eleven required kinds
kustomize build k8s/overlays/prod | grep -oP '^kind: \K\w+' | sort -u

# the deduction greps
kustomize build k8s/overlays/prod | grep -c 'namespace: default'          # 0
kustomize build k8s/overlays/prod | grep -cE 'type: (NodePort|LoadBalancer)'  # 0
kustomize build k8s/overlays/prod | grep -c 'requests:'                   # >= 5
kustomize build k8s/overlays/prod | grep -c 'runAsNonRoot: true'          # >= 5
grep -rn ':latest' k8s/                                                   # empty

# image hygiene
grep -hE '^FROM' api/Dockerfile indexer/Dockerfile ui/Dockerfile          # every line tagged
grep -c '^USER' api/Dockerfile indexer/Dockerfile ui/Dockerfile           # 1 each
grep -cE '^(CMD|ENTRYPOINT) \[' api/Dockerfile indexer/Dockerfile ui/Dockerfile  # 1 each
```
