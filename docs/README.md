# Milestones

Each document states a contract, its result, the **controls that had to fail**, the limits
of what it establishes, and how to reproduce it. They are the reason the claims in the
[README](../README.md) are narrow: each one was written to say what it does *not* prove.

| Document | What it establishes |
| --- | --- |
| [G0](G0_REFERENCE.md) | Real integration with Reticulum/LXMF; messages survive the propagation nodes crashing |
| [G1](G1_INTEGRATION.md) | Persistent mailbox, receipts, a closed protocol |
| [G2](G2_PARTS.md) | Complementary parts. **Closed with no general advantage** — the record says so |
| [G3](G3_GENERATIONS.md) | Nodes outlive whoever created them, across two complete generations |
| [G4](G4_INDEPENDENCE.md) | Delivery with the IP stack cut, and the control that fails when the cut did not happen |
| [V1](V1_CUSTODY.md) | Signed custody: proof of entry and localizable pendency, plus the [receipt returning](V1_RECEIPT_RETURN.md) |
| [V2](V2_REPRODUCTION.md) | A reproduction guide followed on an independent machine |
| [V3a](V3A_BENCH.md) | Two machines, isolated windows, rendezvous by declared instant |
| [V3c](V3C_BENCH.md) | An object crossed a medium carrying **no IP**, the recipient proved to hold no IP interface |

The artifacts they cite are in [`../evidence/`](../evidence/README.md). The bench that
produced them is in [dethron-research](https://github.com/elSilveira/dethron-research).

Numbers in these documents are kept as they were measured, including suite counts from a
tree that no longer exists. Where that is the case, the document says so rather than being
quietly updated.
