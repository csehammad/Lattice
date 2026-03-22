"""Sanctions screening service with a configurable watchlist."""

from __future__ import annotations

from tests.services.common import Result


class SanctionsService:
    def __init__(self) -> None:
        self._watchlist: dict[str, list[str]] = {
            "Sanctioned Corp": ["OFAC", "EU"],
            "Bad Actor Ltd": ["EU"],
            "Blocked Industries": ["OFAC"],
        }
        self.check_count = 0

    def add_to_watchlist(self, entity: str, lists: list[str]) -> None:
        self._watchlist[entity] = lists

    def remove_from_watchlist(self, entity: str) -> None:
        self._watchlist.pop(entity, None)

    async def check(self, *, entity_name: str, country: str) -> Result:
        self.check_count += 1
        matched = self._watchlist.get(entity_name, [])
        score = 85 if matched else max(5, hash(entity_name) % 30)
        return Result(
            clear=len(matched) == 0,
            score=score,
            matched_lists=list(matched),
        )
