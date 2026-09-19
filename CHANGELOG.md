# Changelog

This project follows [Semantic Versioning](https://semver.org/). Until 1.0 the wire
format may change, but `APPLICATION` in `protocol.py` is frozen: changing it would stop
this code verifying the evidence already published, which is the point of publishing it.

## 0.1.0 — unreleased

First release. Extracted from the research bench that produced the evidence, with the
pieces an outsider can actually use.

### Added

- `dethron.Node`: a running Reticulum/LXMF node with synchronous `send`, `custody_of`,
  `fetch`, `collect` and `publish_receipt`.
- The `dethron` command line: `identity`, `relay`, `send`, `fetch`, `receipts`, `verify`.
- `dethron verify`, which recomputes every proof from the files on disk and checks each
  packet inside the validity window it declared for itself.
- `wire.declared_expiry`, so a proof that was sound when it was made stays checkable
  after it expires.
- `evidence/`, the artifacts the milestone documents cite.

### Verified on

Windows 11 with Python 3.10.11, and Ubuntu 24.04 with Python 3.12.3, against rns 1.5.4 and
lxmf 1.1.1. The unit suite and the end-to-end delivery test pass on both. The milestone
evidence in `evidence/` was produced on Windows.

### Known limits

One message, one relay, one recipient; no key exchange or discovery; the hostile relay is
simulated rather than met. The milestone documents in `docs/` each carry a "Limits"
section, and they are the honest answer to what this does not do.
