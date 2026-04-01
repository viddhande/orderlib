# orderlib

Minimal Python project designed for CI/CD:
- Build wheel (.whl)
- Unit tests + Functional tests + Performance tests
- SonarQube scan
- Docker image build
- Push wheel + image to Nexus
- GitOps deployment via Argo CD

Endpoints:
- GET / -> Hello message
- GET /health -> {"status":"ok"}
