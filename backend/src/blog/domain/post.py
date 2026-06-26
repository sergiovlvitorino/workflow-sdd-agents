"""Entidade Post — domínio puro, sem framework/I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


class PostStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Post:
    id: str
    title: str
    content: str
    status: PostStatus
    created_at: datetime
    published_at: datetime | None

    def publish(self, now: datetime) -> Post:
        """Transição draft → published. Idempotente por estado (ADR-0004 §8).

        - DRAFT → retorna novo Post com status=PUBLISHED, published_at=now.
        - PUBLISHED → no-op: retorna self (published_at INALTERADO).
        `now` é o relógio injetado (nunca datetime.now() interno).
        """
        if self.status is PostStatus.PUBLISHED:
            return self  # guarda de no-op — mutation-âncora
        return replace(self, status=PostStatus.PUBLISHED, published_at=now)

    @staticmethod
    def create(
        title: str,
        content: str,
        *,
        new_id: str,
        now: datetime,
    ) -> Post:
        """Fábrica com relógio e id-gen injetados (não usa now()/uuid interno)."""
        return Post(
            id=new_id,
            title=title,
            content=content,
            status=PostStatus.DRAFT,
            created_at=now,
            published_at=None,
        )
