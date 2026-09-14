# Security Policy

## Reporting a vulnerability

Please do not publicly disclose suspected security vulnerabilities through GitHub issues, discussions or other public channels before they have been reviewed.

Report security vulnerabilities privately through [GitHub Security Advisories](https://github.com/katalon-collections/katalon/security/advisories/new) (repository's Security → Report a vulnerability function).

Please include, where possible:

- the affected Katalon version or commit,
- a description of the vulnerability,
- steps required to reproduce it,
- the potential impact,
- relevant configuration information,
- suggested mitigations, if known.

Please avoid including real personal, confidential or production data in vulnerability reports.

## Supported versions

Security fixes are generally provided for the current released version of Katalon. Older releases may no longer receive security updates. Operators should therefore keep Katalon and its dependencies reasonably up to date.

No fixed response or remediation time is guaranteed.

## Deployment security

Katalon is self-hosted software. A secure production deployment depends substantially on the surrounding infrastructure and configuration.

Operators should at minimum ensure:

- HTTPS/TLS for externally accessible installations,
- secure authentication and authorization,
- restricted administrative access,
- securely generated and stored secrets,
- network-level protection of databases and internal services,
- regular software and dependency updates,
- appropriate filesystem and object-storage permissions,
- regular backups,
- tested restoration procedures,
- monitoring of relevant services.

Example or development configurations included in the repository (e.g. `docker-compose.dev.yml`, `.env.example`) may not be suitable for direct production use.

## Data protection

Security controls alone do not establish compliance with data-protection law.

Operators are responsible for assessing which personal or confidential data may be processed through their installation and which legal, organizational and technical requirements apply.

## Dependencies

Katalon relies on third-party libraries, container images and infrastructure components.

Security vulnerabilities may therefore arise in Katalon itself or in its dependencies. Operators should monitor and update both.

## Disclosure

After a vulnerability has been investigated and, where necessary, a fix has been made available, details may be published through a GitHub Security Advisory or release notes.

Responsible disclosure is appreciated.
