"""Abstract Memory interface (Phase 1: stub — not implemented).

Responsibilities:
- Defines MemoryStore abstract base class: store(key, value), retrieve(query), list().
- Exists to establish the contract so future implementations (vector store,
  episodic memory, RSI scratchpad) slot in without modifying the agent core.
- No concrete implementation in Phase 1.
"""
