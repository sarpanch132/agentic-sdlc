# Reviewed pure-Python dependency wheels

These wheels remove six source-only dependency blockers without running source builds on a new device. Exact unmodified corresponding source archives and their full notices are included in sources/ and notices/. manifest.json records source and wheel SHA-256 hashes, Python/build versions and SOURCE_DATE_EPOCH=315532800. No native executable or extension is included.

Actual build environment: CPython3.12.14, pip26.2.2, setuptools84.2.1, wheel0.48.0, packaging26.3. The complete hash lock is build-requirements.lock. bootstrap-pip.json identifies the verified pip bootstrap wheel. Build dependencies were checked against OSV before use. Source archive members were checked for unsafe paths/links before building.

To rebuild, create your own isolated virtual environment, install the exact hash-locked build tools, set SOURCE_DATE_EPOCH to315532800, then run:

    python -I -m pip wheel --no-cache-dir --no-build-isolation --no-deps --no-index --wheel-dir rebuilt sources/PACKAGE.tar.gz

The no-deps option applies only to wheel construction with the complete reviewed build toolchain. Runtime installations still resolve and hash-check their complete dependency closures.

## func-timeout file-level licensing and replacement

func-timeout4.3.5 runtime files and its original LICENSE specify LGPLv3; setup.py specifies LGPLv2.1. Upstream package metadata says v2 and is inconsistent. Original source, headers, metadata and notices are preserved unchanged. Full GPLv3, LGPLv3 and LGPLv2.1 texts are provided in licenses/. The root project MIT license does not relicense this component. Keep the exact corresponding source beside the wheel wherever distributing it.

You may modify the library and rebuild a compatible wheel in your own environment. Install that modified wheel with your environment's pip using --force-reinstall, and run the dependent application with that environment's Python. Modification and reverse engineering for debugging such modifications are not prohibited. The managed installer's integrity checks may reject modified managed files; they do not restrict this separate modification/replacement route. Retain applicable notices and provide modified corresponding source when redistributing your version.

IBM core includes additional vendored notices; retain its complete NOTICE rather than assuming every file is Apache-only.
