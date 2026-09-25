"""The `catalyst-ai` entry point: serve · check · migrate · reembed · retention · worker."""

import argparse
import asyncio
import re
import signal
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError

from catalyst_ai.app import create_app, create_ops_app, default_runtime, job_runners
from catalyst_ai.config import Settings, UnknownSettingsError, load_settings
from catalyst_ai.platform.auth import KeyRegistry, PublicKeyConfigError
from catalyst_ai.platform.jobs import Worker
from catalyst_ai.platform.logging import configure_logging
from catalyst_ai.platform.observability import SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
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
    runtime = default_runtime(settings)
    app = create_app(settings, runtime)
    ops = create_ops_app(settings, runtime)
    servers = []
    for target, addr in ((app, settings.http_addr), (ops, settings.ops_addr)):
        host, port = _split_addr(addr)
        config = uvicorn.Config(
            target,
            host=host,
            port=port,
            log_config=None,
            access_log=False,
            timeout_graceful_shutdown=settings.shutdown_drain_seconds,
        )
        servers.append(uvicorn.Server(config))
    stop = asyncio.Event()
    _install_stop(stop)
    serving = [asyncio.create_task(server.serve()) for server in servers]
    await stop.wait()
    for target in (app, ops):
        target.state.draining = True
    for server in servers:
        server.should_exit = True
    await asyncio.gather(*serving)


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
            settings = load_settings()
            KeyRegistry.from_config(settings.auth_public_keys)
        except (ValidationError, PublicKeyConfigError, UnknownSettingsError) as error:
            print(f"check: settings invalid\n{error}")
            return EXIT_FAIL
        print("check: settings valid; the backend's public keys load")
    return EXIT_OK


def _login(settings: Settings, own: SecretStr | None) -> str:
    """Return the process's own login; in development it may be serve's."""
    return (own or settings.database_url).get_secret_value()


async def _migrate(settings: Settings) -> int:
    owner = _login(settings, settings.database_migrate_url)
    applied = await migrate(owner, Path.cwd() / MIGRATIONS)
    print(f"migrate: {len(applied)} applied " + " ".join(applied))
    return EXIT_OK


async def _job(settings: Settings, command: str) -> int:
    runtime = default_runtime(settings, dsn=_login(settings, settings.database_worker_url))
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
            purged = await runtime.jobs.purge_jobs(runtime.clock.now())
            print(f"retention: {purged} expired job results purged")
    finally:
        await storage.close()
    print(f"{command}: {report.organizations} organisations, {report.documents} documents")
    return EXIT_OK


def _install_stop(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for name in ("SIGTERM", "SIGINT"):
        number = getattr(signal, name, None)
        if number is None:
            continue
        try:
            loop.add_signal_handler(number, stop.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(number, lambda *_: stop.set())


def assemble_worker(settings: Settings, runtime: RuntimeContext) -> tuple[FastAPI, Worker]:
    """Build the worker and the ops port on one registry, so what it counts a scrape shows."""
    ops = create_ops_app(settings, runtime)
    worker = Worker(
        runtime,
        runtime.jobs,
        job_runners(),
        KeyRegistry.from_config(settings.auth_public_keys),
        SecurityCounters(ops.state.metrics),
    )
    ops.state.worker = worker
    return ops, worker


async def _worker(settings: Settings) -> int:
    """Run the worker: claim, verify the stored proof, execute; drain on SIGTERM."""
    runtime = default_runtime(settings, dsn=_login(settings, settings.database_worker_url))
    storage = runtime.storage
    if not isinstance(storage, PostgresStorage):
        return EXIT_FAIL
    await storage.connect()
    ops, worker = assemble_worker(settings, runtime)
    host, port = _split_addr(settings.ops_addr)
    server = uvicorn.Server(
        uvicorn.Config(ops, host=host, port=port, log_config=None, access_log=False)
    )
    stop = asyncio.Event()
    _install_stop(stop)
    serving = asyncio.create_task(server.serve())
    try:
        await worker.serve(stop)
    finally:
        server.should_exit = True
        await serving
        await storage.close()
    return EXIT_OK


async def _serve_ok(settings: Settings) -> int:
    await _serve(settings)
    return EXIT_OK


def _run_command(command: str, settings: Settings) -> int:
    commands: dict[str, Callable[[Settings], Coroutine[Any, Any, int]]] = {
        "serve": _serve_ok,
        "migrate": _migrate,
        "worker": _worker,
    }
    if command in commands:
        return asyncio.run(commands[command](settings))
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
    return _with_settings(args.command)


def _with_settings(command: str) -> int:
    try:
        settings = load_settings()
    except UnknownSettingsError as error:
        print(f"{command}: {error}")
        return EXIT_FAIL
    configure_logging(settings.log_level.value)
    try:
        return _run_command(command, settings)
    except StorageUnavailableError as error:
        print(f"{command}: the database did not answer ({error})")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
