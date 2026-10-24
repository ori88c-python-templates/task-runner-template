"""Errors the GitHub adapter translates from the GitHub API."""


class GithubOrganizationNotFoundError(Exception):
    """The configured organization does not exist or is not visible to the caller.

    GitHub's Search API answers an unknown or inaccessible org with HTTP 422, not 404.
    The adapter turns that into this error so callers do not have to know the status
    code.

    Attributes:
        org: The organization login that was requested.
    """

    def __init__(self, org: str) -> None:
        """Record which organization could not be found.

        Args:
            org: The login that was sent to GitHub.
        """
        self.org = org
        super().__init__(f"GitHub organization {org!r} was not found or is not accessible.")
