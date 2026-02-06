{{/*
Expand the name of the chart.
*/}}
{{- define "wasmcloud.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "wasmcloud.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "wasmcloud.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "wasmcloud.labels" -}}
helm.sh/chart: {{ include "wasmcloud.chart" . }}
{{ include "wasmcloud.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "wasmcloud.selectorLabels" -}}
app.kubernetes.io/name: {{ include "wasmcloud.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Actor labels - adds actor-specific labels
*/}}
{{- define "wasmcloud.actorLabels" -}}
{{ include "wasmcloud.labels" . }}
app.kubernetes.io/component: actor
{{- end }}

{{/*
Provider labels - adds provider-specific labels
*/}}
{{- define "wasmcloud.providerLabels" -}}
{{ include "wasmcloud.labels" . }}
app.kubernetes.io/component: provider
{{- end }}

{{/*
Generate NATS URL with fallback
*/}}
{{- define "wasmcloud.natsUrl" -}}
{{- if .Values.wasmcloud.host.nats.url -}}
{{ .Values.wasmcloud.host.nats.url }}
{{- else -}}
nats://nats.{{ .Release.Namespace }}.svc.cluster.local:4222
{{- end -}}
{{- end }}

{{/*
Generate Redis URL with fallback
*/}}
{{- define "wasmcloud.redisUrl" -}}
{{- if .Values.providers.standard.redis.config.url -}}
{{ .Values.providers.standard.redis.config.url }}
{{- else -}}
redis://redis-master.{{ .Release.Namespace }}.svc.cluster.local:6379
{{- end -}}
{{- end }}

{{/*
Generate actor WASM path
*/}}
{{- define "wasmcloud.actorWasmPath" -}}
{{- $actor := . -}}
{{- printf "/wasmcloud/%s/%s" $actor.wasmPath $actor.wasmFile -}}
{{- end }}

{{/*
Generate provider image path
*/}}
{{- define "wasmcloud.providerImagePath" -}}
{{- $provider := . -}}
{{- printf "file:///wasmcloud/%s/%s" $provider.imagePath $provider.imageFile -}}
{{- end }}

{{/*
Check if actor has capability
*/}}
{{- define "wasmcloud.hasCapability" -}}
{{- $actor := index . 0 -}}
{{- $capability := index . 1 -}}
{{- if has $capability $actor.capabilities -}}
true
{{- else -}}
false
{{- end -}}
{{- end }}

{{/*
Generate resource configuration for actors
*/}}
{{- define "wasmcloud.actorResources" -}}
limits:
  cpu: {{ .Values.resources.actors.limits.cpu }}
  memory: {{ .Values.resources.actors.limits.memory }}
requests:
  cpu: {{ .Values.resources.actors.requests.cpu }}
  memory: {{ .Values.resources.actors.requests.memory }}
{{- end }}

{{/*
Generate resource configuration for providers
*/}}
{{- define "wasmcloud.providerResources" -}}
limits:
  cpu: {{ .Values.resources.providers.limits.cpu }}
  memory: {{ .Values.resources.providers.limits.memory }}
requests:
  cpu: {{ .Values.resources.providers.requests.cpu }}
  memory: {{ .Values.resources.providers.requests.memory }}
{{- end }}