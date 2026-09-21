"""The translate pipeline: the target rule, the door, the fences, the response."""

import pytest

from catalyst_ai.capabilities.translate import descriptor, run
from catalyst_ai.capabilities.translate.pipeline import assemble, parse, require_target
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.translate.conftest import (
    FIELD,
    FIELD_AR,
    make_request,
    translation_text,
)


async def test_run_translates_a_field_keeping_structure_and_keys() -> None:
    provider = ScriptedProvider([translation_text()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert response.translated_text == FIELD_AR
    assert response.detected_language == "en"
    assert response.target_language == "ar"
    assert response.structure_preserved is True
    assert response.confidence == 1.0
    assert response.capability_version == descriptor.version
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True


async def test_a_request_without_a_target_is_refused_before_any_call() -> None:
    provider = ScriptedProvider([translation_text()])
    with pytest.raises(Error) as caught:
        await run(make_request(target_language=None), make_runtime(provider), "r")
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert caught.value.details[0].code == "target_language_required"
    assert provider.calls == []
    with pytest.raises(Error):
        require_target(make_request(target_language=None))


def test_assemble_names_the_languages_and_fences_text_and_context() -> None:
    parsed = parse(make_request(context="A bug report.", source_language="en"), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([translation_text()])))
    developer = generate.segments[1].text
    assert "Source language: en" in developer
    assert "Target language: ar" in developer
    assert "Mode: field" in developer
    assert generate.segments[2].text.startswith("<<<text>>>")
    assert "A bug report." in generate.segments[3].text
    detect = assemble(parse(make_request(), "rid", None), make_runtime(ScriptedProvider(["{}"])))
    assert "Source language: detect it" in detect.segments[1].text


async def test_title_mode_returns_one_line_and_the_door_holds() -> None:
    provider = ScriptedProvider([translation_text("زر  تسجيل\nالدخول معطل", "en")])
    response = await run(
        make_request(mode="title", text="Login button broken"), make_runtime(provider), "r"
    )
    assert "\n" not in response.translated_text
    assert response.structure_preserved is True
    off = make_runtime(
        ScriptedProvider([translation_text()]),
        make_settings(capability_translate=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED


async def test_a_translation_with_a_foreign_key_is_unsafe() -> None:
    provider = ScriptedProvider([translation_text(FIELD_AR.replace("PRJ-42", "OTHER-9"))])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
    assert FIELD.count("PRJ-42") == 1
