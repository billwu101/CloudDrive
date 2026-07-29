"""Unauthenticated guest access to public share links (proposal §28).

Kept apart from ``app.share`` on purpose: this is the only package in the
backend whose routes must never depend on ``CurrentUserId``, and mixing it with
the owner-facing share management routes makes that easy to get wrong.
"""
