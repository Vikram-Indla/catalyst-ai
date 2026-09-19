"""The door: the switch, the version, the scanner, the cap, and the two kinds of key."""

from uuid import uuid4

import pytest

from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Door, admit
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    ScriptedProvider,
    make_runtime,
    make_settings,
)


def _door(
    settings: CapabilitySettings | None = None,
    capability_version: str = "1.2.3",
    user_texts: dict[str, str | None] | None = None,
    idempotency: str | None = None,
) -> Door:
    return Door(
        name="x",
        version="1.0.0",
        prompt_version="1",
        alias="text-default",
        settings=settings or CapabilitySettings(),
        organization_id=uuid4(),
        capability_version=capability_version,
        user_texts=user_texts if user_texts is not None else {"title": "fine"},
        canonical_input={"a": 1},
        idempotency=idempotency,
    )


def test_admit_returns_a_content_key_or_an_idempotency_key() -> None:
    runtime = make_runtime(ScriptedProvider([GOOD_TEXT]))
    content_key = admit(_door(), runtime)
    idem_key = admit(_door(idempotency="abc"), runtime)
    assert content_key != idem_key
    assert admit(_door(), runtime) != content_key


def test_admit_refuses_the_switch_the_version_and_the_scanner() -> None:
    runtime = make_runtime(ScriptedProvider([GOOD_TEXT]))
    with pytest.raises(Error) as off:
        admit(_door(settings=CapabilitySettings(enabled=False)), runtime)
    assert off.value.code is ErrorCode.CAPABILITY_DISABLED
    with pytest.raises(Error) as version:
        admit(_door(capability_version="2.0.0"), runtime)
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH
    with pytest.raises(Error) as scanned:
        admit(_door(user_texts={"t": "someone@example.com"}), runtime)
    assert scanned.value.code is ErrorCode.INPUT_REJECTED


def test_admit_refuses_over_the_cap() -> None:
    runtime = make_runtime(
        ScriptedProvider([GOOD_TEXT]), make_settings(tenant_budget_default_micros_per_day=1)
    )
    with pytest.raises(Error) as caught:
        admit(_door(), runtime)
    assert caught.value.code is ErrorCode.BUDGET_EXCEEDED
