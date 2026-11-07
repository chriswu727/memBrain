# Native runtime resources

These resources contain pgvector 0.8.6 and, on macOS/Windows, OpenSSL 3.5.9 LTS
compiled against the reviewed PostgreSQL 16.15 distribution. Linux overlays also
contain libxml2 built from Ubuntu's security-patched 2.9.13+dfsg-1ubuntu0.14 source.
They contain no
PostgreSQL server executable. The optional PostgreSQL supplier package is
installed separately; its Python extraction wrapper is never executed.

pgvector is distributed under the PostgreSQL License. OpenSSL is distributed
under the Apache License 2.0. Each overlay includes the original component
licenses and OpenSSL authors in `share/licenses/`. The original PostgreSQL
distribution and its licenses remain in the separately installed supplier
package and in the prepared private cache.

Linux libxml2 includes its upstream and Debian copyright/license documents and
source/build provenance in `share/licenses/libxml2/`. Previous Linux manifests
are retained for exact engine bindings; their missing XML dependency is loaded
from a separate verified cache without modifying the bound engine or journal.

`index.json` records each reviewed build artifact, supplier archive checksum,
overlay checksum and expected full native file manifest. The source/build and
packaging tools are `scripts/build_native_bundle.py` and
`scripts/package_native_resources.py` in the memBrain source repository.

Source projects:

- PostgreSQL: https://www.postgresql.org/
- pgvector: https://github.com/pgvector/pgvector
- OpenSSL: https://github.com/openssl/openssl
- libxml2: https://gitlab.gnome.org/GNOME/libxml2
- Ubuntu libxml2 source: https://packages.ubuntu.com/source/jammy/libxml2
- Supplier packaging: https://github.com/leontrolski/postgresql-binaries

These files support the ongoing native integration candidate. Their presence
does not change the selected database engine or establish release acceptance.
