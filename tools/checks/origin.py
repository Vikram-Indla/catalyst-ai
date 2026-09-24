"""ARCH-009 §1 and §5: the service verifies and never signs, and a secret is read in one place.

Four rules over `src/`: a signing primitive is never imported and no key is ever generated
(the private key exists only in the backend); the cryptography package is imported by one
module, the key registry; and no code path reads a service token or a bearer — the words
themselves may not appear, so a fallback cannot creep back. One module is excepted, and only
for the word: the provider's credentials module forms the authorization header of the provider,
from the token the runtime's own identity is issued; the backend's door never sees it. And every
secret of the settings is read by exactly one module — the provider's credentials module its
token, the entry points the database URL — so a second reader is a decision, not an accident.
The settings module itself declares and validates the secrets, and is not counted a reader;
nor is `config/deployed.py`, where its cross-field validation lives.
"""

from pathlib import Path
from types import MappingProxyType

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative, walk

CRYPTO_MODULE = "cryptography"
KEY_MODULE = rules.SRC / "platform" / "auth" / "keys.py"
SIGNING_NAMES = ("PrivateKey", "generate_private_key", "Ed25519PrivateKey")
SIGNING_CALLS = (".sign(", "PrivateKey.generate(", "private_bytes")
BEARER_WORDS = ("service_token", "SERVICE_TOKEN", "Bearer ", "bearer_token")
PROVIDER_CREDENTIALS = "providers/gemini/credentials.py"
DECLARERS = ("config/settings.py", "config/deployed.py")
SECRET_READERS = MappingProxyType(
    {
        "provider_access_token": ("providers/gemini/credentials.py",),
        "database_url": ("app.py", "cli.py"),
        "database_worker_url": ("cli.py",),
        "database_migrate_url": ("cli.py",),
    }
)


def _violations_in(path: Path, root: Path) -> list[Violation]:
    violations = []
    where = relative(path, root)
    for line, name in imported_names(parse(path)):
        if name.split(".")[0] == CRYPTO_MODULE and path.resolve() != (root / KEY_MODULE).resolve():
            violations.append(Violation(where, line, f"imports {name} outside the key registry"))
        if any(name.endswith(signing) for signing in SIGNING_NAMES):
            violations.append(Violation(where, line, f"imports a signing primitive {name}"))
    for number, source in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if any(call in source for call in SIGNING_CALLS):
            violations.append(Violation(where, number, "signs or mints key material"))
        if any(word in source for word in BEARER_WORDS) and not where.endswith(
            PROVIDER_CREDENTIALS
        ):
            violations.append(Violation(where, number, "reads a service token or a bearer"))
    return violations


def secret_violations(root: Path) -> list[Violation]:
    """Report a module reading a secret that is not the one module allowed to read it."""
    violations = []
    for path in walk(root, rules.SRC):
        where = relative(path, root)
        text = path.read_text(encoding="utf-8")
        for secret, readers in SECRET_READERS.items():
            reads = f".{secret}" in text and ".get_secret_value()" in text
            if reads and not where.endswith((*readers, *DECLARERS)):
                violations.append(Violation(where, 1, f"reads {secret}, which is not its secret"))
    return violations


def run(root: Path) -> list[Violation]:
    """Report any signing primitive, stray cryptography import, bearer or second secret reader."""
    violations: list[Violation] = []
    for path in walk(root, rules.SRC):
        violations += _violations_in(path, root)
    return violations + secret_violations(root)
