"""The `catalyst-ai` entry point: serve · check · migrate · reembed · retention · worker."""

import argparse
import asyncio
import re
import sys
from pathlib import Path

import uvicorn
from pydantic import ValidationError

from catalyst_ai.app import create_app, default_runtime, health
from catalyst_ai.config import Settings, load_settings
from catalyst_ai.platform.logging import configure_logging
from catalyst_ai.platform.storage import PostgresStorage, StorageUnavailableError, migrate
from catalyst_ai.retrieval import WORK_ITEMS, reembed, retention

TOOL_VERSIONS = Path(".tool-versions")
MIGRATIONS = Path("db/migrations")
PYPROJECT = Path("pyproject.toml")
DOCKERFILE = Path("Dockerfile")
EXIT_OK = 0
EXIT_FAIL = 1


def _split_addr(addr: str) -> tuple[str, int]:
    host, _, port = addr.rpartition(":")
    return host or "0.0.0.0", int(port)  # noqa: S104 — the listen address is configuration


async def _serve(settings: Settings) -> None:
    app = create_app(settings)
    ops = create_app(settings)
    ops.include_router(health)
    servers = []
    for target, addr in ((app, settings.http_addr), (ops, settings.ops_addr)):
        host, port = _split_addr(addr)
        config = uvicorn.Config(target, host=host, port=port, log_config=None, access_log=False)
        servers.append(uvicorn.Server(config))
    await asyncio.gather(*(server.serve() for server in servers))


def _declared_python_versions(root: Path) -> dict[str, str]:
    versions = {}
    tool = (root / TOOL_VERSIONS).read_text(encoding="utf-8")
    match = re.search(r"^python (\d+\.\d+)\.\d+$", tool, re.MULTILINE)
    versions[".tool-versions"] = match.group(1) if match else "missing"
    project = (root / PYPROJECT).read_text(encoding="utf-8")
    match = re.search(r'requires-python = ">=(\d+\.\d+),<', project)
    versions["pyproject.toml"] = match.group(1) if match else "missing"
    image = (root / DOCKERFILE).read_text(encoding="utf-8")
    match = re.search(r"^FROM python:(\d+\.\d+)\.", image, re.MULTILINE)
    versions["Dockerfile"] = match.group(1) if match else "missing"
    return versions


def _toolchain_agrees(root: Path) -> bool:
    if not all((root / f).exists() for f in (TOOL_VERSIONS, PYPROJECT, DOCKERFILE)):
        print("check: toolchain files absent (not a repository checkout); settings only")
        return True
    versions = _declared_python_versions(root)
    if len(set(versions.values())) != 1:
        print(f"check: python version disagreement {versions}")
        return False
    print(f"check: python {next(iter(versions.values()))} agreed across three files")
    return True


def check(root: Path, *, load: bool) -> int:
    """Validate the toolchain agreement and, when asked, the environment's settings."""
    if not _toolchain_agrees(root):
        return EXIT_FAIL
    if load:
        try:
            load_settings()
        except ValidationError as error:
            print(f"check: settings invalid\n{error}")
            return EXIT_FAIL
        print("check: settings valid")
    return EXIT_OK


async def _migrate(settings: Settings) -> int:
    applied = await migrate(settings.database_url.get_secret_value(), Path.cwd() / MIGRATIONS)
    print(f"migrate: {len(applied)} applied " + " ".join(applied))
    return EXIT_OK


async def _job(settings: Settings, command: str) -> int:
    runtime = default_runtime(settings)
    storage = runtime.storage
    if not isinstance(storage, PostgresStorage):
        return EXIT_FAIL
    await storage.connect()
    try:
        if command == "reembed":
            report = await reembed(WORK_ITEMS, storage, runtime.provider)
        else:
            report = await retention(
                WORK_ITEMS, storage, runtime.clock, settings.retrieval_document_ttl_days
            )
    finally:
        await storage.close()
    print(f"{command}: {report.organizations} organisations, {report.documents} documents")
    return EXIT_OK


def _run_command(command: str, settings: Settings) -> int:
    if command == "serve":
        asyncio.run(_serve(settings))
        return EXIT_OK
    if command == "migrate":
        return asyncio.run(_migrate(settings))
    return asyncio.run(_job(settings, command))


def main(argv: list[str] | None = None) -> int:
    """Parse the subcommand and run it."""
    parser = argparse.ArgumentParser(prog="catalyst-ai")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "worker", "migrate", "reembed", "retention"):
        commands.add_parser(name)
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--no-env", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(Path.cwd(), load=not args.no_env)
    if args.command == "worker":
        print("worker: unavailable until the jobs table exists")
        return EXIT_FAIL
    return _with_settings(args.command)


def _with_settings(command: str) -> int:
    settings = load_settings()
    configure_logging(settings.log_level.value)
    try:
        return _run_command(command, settings)
    except StorageUnavailableError as error:
        print(f"{command}: the database did not answer ({error})")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
