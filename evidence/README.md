# Published evidence

The artifacts the milestone documents cite. `window/results/` remains the disposable
working directory the probes write into; this is the subset that carries the claims,
so that a reader can **recompute instead of believe**.

| Folder | Milestone |
| --- | --- |
| `gateway-g0-*` | [G0](../docs/G0_REFERENCE.md) — reference integration |
| `gateway-g1-*` | [G1](../docs/G1_INTEGRATION.md) — protocol and mailbox |
| `gateway-g2-*`, `g2-comparison-*` | [G2](../docs/G2_PARTS.md) — parts and reconstruction |
| `gateway-g3-*` | [G3](../docs/G3_GENERATIONS.md) — node generations |
| `gateway-g4-*` | [G4](../docs/G4_INDEPENDENCE.md) — independence from the IP stack |
| `gateway-v1-*` | [V1](../docs/V1_CUSTODY.md) — custody and [receipt](../docs/V1_RECEIPT_RETURN.md) |
| `v3a-network-20260918/` | [V3a](../docs/V3A_BENCH.md) — two-machine bench over the network |
| `v3c-serial-20260918/` | [V3c](../docs/V3C_BENCH.md) — bench over a link with no IP |

## Two provenance caveats

The V3a and V3c reports each carry a `commit` field. In **V3a** it names the code that
**audited** the run, not the code that executed it: that report was born with the field
broken — git was refusing the repository over *dubious ownership* — and was regenerated
later from the same intact evidence. V3c's names the code that actually ran the bench.

G3's `report.json` contains an absolute path holding the Windows username of whoever
ran it. It is part of the message of a **negative control** — a declared credential that
is absent — and was kept exactly as it came out. Editing an artifact to make it
presentable would cost more than the name is worth.
