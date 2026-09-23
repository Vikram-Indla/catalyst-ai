"""`make ci`'s database: the workflow's service container, started from the same pinned values.

The hosted job gets PostgreSQL as a service named `postgres` on the job's network and reaches it
through `CATALYST_AI_EVAL_DATABASE_URL`. Locally the same image, environment and health options
start under the same alias on a network of its own, and the job container joins that network
with the same variable, so both runs reach the database one way. `tools/checks/ci` holds the
workflow to these values.

  up     start the network and the database, and wait until it is healthy
  args   print the arguments the job container needs to reach it
  down   remove both (safe to run when neither exists)
"""

import shlex
import subprocess
import sys
import time

from tools import rules

CONTAINER = f"{rules.CI_NETWORK}-postgres"
HEALTHY_WITHIN_S = 120


def _docker(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["docker", *args], capture_output=True, check=False, encoding="utf-8", errors="replace"
    )
    if check and completed.returncode != 0:
        message = f"docker {args[0]}: {completed.stderr.strip()}"
        raise RuntimeError(message)
    return completed.stdout.strip()


def run_args() -> list[str]:
    """Return the `docker run` arguments that start the database as the workflow declares it."""
    environment = [f"--env={key}={value}" for key, value in rules.CI_DATABASE_ENV.items()]
    return [
        "run",
        "--detach",
        f"--name={CONTAINER}",
        f"--network={rules.CI_NETWORK}",
        f"--network-alias={rules.CI_DATABASE_ALIAS}",
        *environment,
        *shlex.split(rules.CI_DATABASE_OPTIONS),
        rules.CI_DATABASE_IMAGE,
    ]


def job_args() -> list[str]:
    """Return the arguments the job container needs: the network and the job's environment."""
    environment = [f"--env={key}={value}" for key, value in rules.CI_JOB_ENV.items()]
    return [f"--network={rules.CI_NETWORK}", *environment]


def down() -> None:
    """Remove the database and the network, whether or not they exist."""
    _docker("rm", "--force", "--volumes", CONTAINER, check=False)
    _docker("network", "rm", rules.CI_NETWORK, check=False)


def up() -> None:
    """Start the database and return once it reports healthy."""
    down()
    _docker("network", "create", rules.CI_NETWORK)
    _docker(*run_args())
    deadline = time.monotonic() + HEALTHY_WITHIN_S
    while time.monotonic() < deadline:
        if _docker("inspect", "--format={{.State.Health.Status}}", CONTAINER) == "healthy":
            return
        time.sleep(1)
    down()
    message = f"{CONTAINER} was not healthy within {HEALTHY_WITHIN_S} s"
    raise RuntimeError(message)


def main(argv: list[str] | None = None) -> int:
    """Dispatch `up`, `args` or `down`."""
    command = (argv if argv is not None else sys.argv[1:])[:1]
    if command == ["args"]:
        print(" ".join(shlex.quote(arg) for arg in job_args()))
    elif command == ["up"]:
        up()
        print(
            f"ci-postgres: {CONTAINER} healthy on {rules.CI_NETWORK} as {rules.CI_DATABASE_ALIAS}"
        )
    elif command == ["down"]:
        down()
    else:
        print("usage: ci_postgres up | args | down", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
