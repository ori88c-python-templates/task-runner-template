"""The few facts about a repository that the report needs."""

from typing import NamedTuple


class GithubRepoInfo(NamedTuple):
    """One repository, reduced from GitHub's search result to what the report shows.

    A ``NamedTuple`` rather than a Pydantic model: the values are already validated by
    the SDK's response model, so this is an immutable record for passing between the
    adapter that produces it and the writer that consumes it.

    Attributes:
        name: Repository name without the organization prefix.
        stars: Stargazer count, the popularity measure the report ranks by.
        forks: Fork count, the second popularity signal.
        language: Primary language as GitHub reports it, or ``None`` when GitHub
            could not determine one (documentation-only repositories, for example).
    """

    name: str
    stars: int
    forks: int
    language: str | None
