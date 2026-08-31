{{- define "katalon.image" -}}
{{- $repo := .repo -}}
{{- if $.root.Values.image.registry -}}
{{ $.root.Values.image.registry }}/{{ $repo }}:{{ $.root.Values.image.tag }}
{{- else -}}
{{ $repo }}:{{ $.root.Values.image.tag }}
{{- end -}}
{{- end -}}

{{- define "katalon.envCommon" -}}
- name: DATABASE_URL
  value: "postgresql://{{ .Release.Name }}:$(POSTGRES_PASSWORD)@{{ .Release.Name }}-db:5432/katalon"
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-secrets
      key: postgres-password
- name: REDIS_URL
  value: "redis://{{ .Release.Name }}-redis:6379/0"
- name: ELASTICSEARCH_URL
  value: "http://{{ .Release.Name }}-elasticsearch:9200"
- name: CANTALOUPE_URL
  value: "http://{{ .Release.Name }}-cantaloupe:8182"
- name: CANTALOUPE_PUBLIC_URL
  value: {{ .Values.env.cantaloupePublicUrl | quote }}
- name: SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-secrets
      key: secret-key
- name: KATALON_SECRETS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Release.Name }}-secrets
      key: katalon-secrets-key
- name: MEDIA_ROOT
  value: "/var/lib/katalon/media"
{{- end -}}
