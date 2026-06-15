# Authority database integration

Relumine links extracted cultural entities against two external authority sources.

## CBDB

Run:

```bash
python analysis/authority_databases/download_cbdb.py
```

The script reads the official `cbdb-project/cbdb_sqlite` release metadata,
downloads the current SQLite package, verifies its SHA-256 checksum, and extracts
it under `apps/api/ocrforge_web/data/authority/cbdb/`. That directory is ignored
by Git.

## CHGIS

CHGIS is queried through its official read-only Temporal Gazetteer API:

```text
https://chgis.hudci.org/tgaz/placename?n=临川&fmt=json
```

CHGIS V6 permits academic research but prohibits redistribution. Relumine stores
only the small match records returned for analyzed entities, including the
CHGIS identifier, validity years, feature type, parent jurisdiction, coordinates,
and canonical source URL. It does not redistribute the CHGIS dataset.
