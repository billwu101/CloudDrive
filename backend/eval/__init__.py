"""Assistant verification & scoring harness (E1 skeleton).

See doc/assistant-eval-design.md. This package provides the eval-case schema,
a deterministic verifier + scoring, a report renderer, and an API runner that
drives a live backend's /assistant/chat. The in-process mock-LLM runner for
fully deterministic CI runs is a follow-up within E1.
"""
