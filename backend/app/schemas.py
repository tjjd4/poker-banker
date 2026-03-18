"""Shared Pydantic/FastAPI schemas used across multiple modules."""

from typing import Annotated

from fastapi import Query


class PaginationParams:
    def __init__(
        self,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        self.offset = offset
        self.limit = limit
