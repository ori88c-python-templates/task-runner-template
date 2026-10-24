# distribution

The installed Python distribution that provides the `app` import. Callers import
`from app.distribution import installed_app_version`.

This is not configuration (nothing here is env-overridable) and not logging
(`LogManager` only stamps the version string it is given). Wheel installs are
resolved through `importlib.metadata.packages_distributions`; editable `uv`
installs through a `.pth` that points at `src/`.

The version comes from installed package metadata (populated from
`pyproject.toml` at install time), not from reading the toml file at runtime.
