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
python -m crawl_service collect-all
python -m crawl_service pipeline
python -m crawl_service validate-handoff --fixtures-only
python -m crawl_service validate-handoff --production-only
```

The older root scripts remain as deprecated compatibility wrappers.

## Shared inputs and root outputs

- Source registry: `config/sources.yaml`
- Canonical taxonomy: `backend/shared/taxonomy.json`
- Raw/interim/processed data: `data/`
- Quality and coverage reports: `reports/`

The service does not create a private taxonomy, data directory, or report
directory. Core, Profile, and Recommendation consumers use the shared taxonomy,
market contracts, fixtures, and processed warehouse tables; they do not import
the service's internal models.

TopCV remains disabled because of its access challenge. ViecOi collection stays
limited to three public listing pages with detail pages disabled. Collectors do
not bypass CAPTCHA, Cloudflare, authentication, or access controls.

The current snapshot describes only the monitored sources and must not be
presented as the entire Vietnamese labour market. No trend or growth claim is
made without historical snapshots.
