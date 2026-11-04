# Vendored browser libraries

The memory page loads these files from the package itself (`/static/vendor/...`). Nothing is fetched from a CDN or
any other host at runtime. `tests/test_observatory.py` checks every file below against the SHA-256 recorded here.

## three.js 0.186.1 (MIT)

Used by `observatory.js`, the 3D view of the memory map. Only the WebGL ES-module build is vendored; the WebGPU,
TSL and CommonJS builds and the `examples/` add-ons (including `OrbitControls`) are not. The camera controls are
written in `observatory.js`, so no bare `three` import specifier (and no inline import map, which the page's
Content-Security-Policy would block) is needed.

- Source: npm registry, `https://registry.npmjs.org/three/-/three-0.186.1.tgz`, published 2026-09-24
- Tarball sha256: `8cd068708ea44f2c73c944b1cead2ba2f0d5c15c8fc194e5700f4e4f4a033fe7`
- Tarball integrity (npm): `sha512-blFeqb49wRCSGUGj7gtpfnSGHy2lwDk94RhUmS1c/hTby70kvChbWpkJ4Pm1390LqzzvTmzgXKHPEafJwCb8jA==`
- Files, copied unmodified from the tarball's `package/` directory:

| Path here | From the tarball | sha256 |
| --- | --- | --- |
| `three/three.module.js` | `package/build/three.module.js` | `9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea` |
| `three/three.core.js` | `package/build/three.core.js` | `9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6` |
| `three/LICENSE` | `package/LICENSE` | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |

To update: download the new tarball from the registry, copy the same three files, and update the version, URLs and
hashes here and in `tests/test_observatory.py`.
