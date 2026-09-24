"""Where tenant text may be processed: an in-Kingdom region of Vertex AI, nowhere else.

The region is configuration (`PROVIDER_VERTEX_LOCATION`), never a literal in the code that calls
the provider: the endpoint is built from it, and adding a region is a configuration change. What
stays in code is the residency rule itself, the allowlist of in-Kingdom locations; a location
outside it is refused in every environment. The provider's regional endpoint processes a request
in its region; the Developer API and the global or multi-region endpoints do not promise that.
In staging and production the settings therefore also refuse a missing location, an origin other
than the location's own endpoint, a missing project, and a developer's token (a deployed process
authenticates as its own workload identity). Development may point at a proxy or a recording,
and a developer may use their own short-lived token.
"""

IN_KINGDOM_LOCATIONS = frozenset({"me-central2"})
ENDPOINT_TEMPLATE = "https://{location}-aiplatform.googleapis.com"
DEVELOPMENT_LOCATION = sorted(IN_KINGDOM_LOCATIONS)[0]


def regional_endpoint(location: str) -> str:
    """Return the provider's regional origin for the location."""
    return ENDPOINT_TEMPLATE.format(location=location)


def residency_problem(
    deployed: bool,
    location: str | None,
    origin_override: str | None,
    project: str,
    developer_token: bool,
) -> str | None:
    """Return why the process would send tenant text outside the Kingdom, or None."""
    if location is not None and location not in IN_KINGDOM_LOCATIONS:
        return f"PROVIDER_VERTEX_LOCATION {location} is not an in-Kingdom location"
    if not deployed:
        return None
    endpoint = regional_endpoint(location) if location else None
    problems = (
        (location is None, "PROVIDER_VERTEX_LOCATION is required outside development"),
        (
            origin_override is not None and origin_override.rstrip("/") != endpoint,
            "the provider's origin must be the location's regional endpoint",
        ),
        (not project, "PROVIDER_VERTEX_PROJECT is required outside development"),
        (developer_token, "a deployed process uses its workload identity, not a developer's token"),
    )
    return next((reason for failed, reason in problems if failed), None)
