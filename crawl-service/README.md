# Career Compass crawl service

This service owns the production Hiring Data Layer: source collection, cleaning,
normalization, extraction, lifecycle tracking, aggregation, quality reporting,
and downstream handoff validation.

## Local installation

From the repository root:

```powershell
pip install -e .\crawl-service
```

## Commands

```powershell
python -m crawl_service status
python -m crawl_service collect-greenhouse
python -m crawl_service collect-viecoi
python -m crawl_service collect-onet
python -m crawl_service enrich-onet-vi
python -m crawl_service collect-all
python -m crawl_service pipeline
python -m crawl_service publish-db
python -m crawl_service validate-handoff --fixtures-only
python -m crawl_service validate-handoff --production-only
```

With Docker Compose, the image entrypoint already supplies
`python -m crawl_service`, so pass only the subcommand:

```powershell
docker compose run --rm crawl-service collect-all
docker compose run --rm crawl-service pipeline
```

The older root scripts remain as deprecated compatibility wrappers.

## Shared inputs and root outputs

- Source registry: `config/sources.yaml`
- Canonical taxonomy: `backend/shared/taxonomy.json`
- Raw/interim/processed data: `data/`
- Quality and coverage reports: `reports/`

Canonical processed tables are also published to the Postgres schema configured
by `CRAWL_DATABASE_SCHEMA`. `publish-db` republishes existing Parquet outputs
without running collectors. Parquet remains the auditable handoff artifact while
Postgres is the runtime source for backend consumers.

TopCV remains disabled because of its access challenge. ViecOi collection stays
limited to three public listing pages with detail pages disabled. Collectors do
not bypass CAPTCHA, Cloudflare, authentication, or access controls.

The current snapshot describes only the monitored sources and must not be
presented as the entire Vietnamese labour market. No trend or growth claim is
made without historical snapshots.
