"""Three database logins, one per process, so the request-facing one holds the least.

`serve` (`DATABASE_URL`) is a member of the application role only: it cannot read another
organisation, and it cannot migrate. The worker (`DATABASE_WORKER_URL`) adds the maintenance role
its claim, its purge and the index jobs need. The owner (`DATABASE_MIGRATE_URL`) is used by
`catalyst-ai migrate` alone. Outside development all three are required and name three different
users; development may run every process as one login. And outside development no login's
password may be its own user name: that is the shape of the compose file's local passwords
(`db/provision/development.sql`), so a development credential can never start a deployed process.
"""

from urllib.parse import urlsplit

LOGINS = 3


def user_of(url: str) -> str:
    """Return the user a connection string logs in as (empty when it names none)."""
    return urlsplit(url).username or ""


def named_after_itself(url: str) -> bool:
    """Return whether the connection string's password is its user name (a development login)."""
    parts = urlsplit(url)
    return bool(parts.username) and parts.password == parts.username


def logins_problem(deployed: bool, serve: str, worker: str | None, owner: str | None) -> str | None:
    """Return why the processes would share a login outside development, or None."""
    if not deployed:
        return None
    urls = (serve, worker or "", owner or "")
    users = {user_of(url) for url in urls}
    problems = (
        (
            worker is None or owner is None,
            "DATABASE_WORKER_URL and DATABASE_MIGRATE_URL are required outside development",
        ),
        (
            len(users) != LOGINS or "" in users,
            "serve, the worker and the migration must log in as three different users",
        ),
        (
            any(named_after_itself(url) for url in urls),
            "a login whose password is its user name is a development login",
        ),
    )
    return next((reason for failed, reason in problems if failed), None)
