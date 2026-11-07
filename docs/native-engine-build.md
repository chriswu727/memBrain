# Native engine build for qualification

The desktop runtime currently uses PostgreSQL and pgvector binaries from pgserver. Its PostgreSQL 16.2 security baseline blocks release. The experimental builder below prepares a separate `membrain-postgres` wheel; it does not update dependencies, select the new engine, upgrade user profiles or publish anything.

On macOS with Python 3.12+, Xcode Command Line Tools, make and codesign, choose a new build directory without spaces and a separate artifact directory:

```sh
python scripts/build_embedded_postgres.py \
  --work-directory /tmp/membrain-native-build \
  --output-directory /tmp/membrain-native-wheels \
  --jobs 4
```

The fixed PostgreSQL and pgvector source archives must match the checksums in the script. The builder retains its build directory and writes build output to standard output; it refuses an occupied build directory. Build on the target architecture. It bundles relative native libraries, upstream licenses and file/RECORD hashes. Its ad-hoc signing enables local execution and does not provide publisher identity or notarization. Linux and Windows builders are not implemented here.

Use the resulting artifact only in isolated qualification profiles. Replacing PostgreSQL binaries does not by itself repair old system catalogs: review the intervening minor release notes, preserve a verified backup, and validate the supported maintenance/recovery flow before changing an installation. [Measured compatibility, installation results and remaining gates](../evaluations/maturity-native-engine-2026-11-04.md) distinguish the tested Mac artifact from the unchanged distributed runtime.
