"""Speech adapters: AWS profile mapping, provider selection, streaming semantics.

The AWS adapters drive Pipecat's ``[aws]`` services, which need the extra and
credentials at runtime; the profile mapping, provider selection, and streaming
contract are exercised here with the configuration and the in-memory doubles.
"""

from __future__ import annotations

import pytest

from onecx_pipecat.adapters.factory import build_stt, build_tts
from onecx_pipecat.adapters.speech import (
    AwsSttAdapter,
    AwsTtsAdapter,
    InMemorySttAdapter,
    InMemoryTtsAdapter,
    UnsupportedLanguageError,
    resolve_profile,
)
from onecx_pipecat.config import AwsSpeechProfile, Settings, SpeechSettings


def _speech() -> SpeechSettings:
    return SpeechSettings(
        region="eu-west-1",
        default_language="en",
        aws_profiles={
            "en": AwsSpeechProfile(transcribe_language="en-US", polly_voice="Joanna"),
            "de": AwsSpeechProfile(transcribe_language="de-DE", polly_voice="Marlene"),
        },
    )


def test_resolve_profile_maps_the_pinned_language():
    profile = resolve_profile(_speech(), "de")
    assert (profile.transcribe_language, profile.polly_voice) == ("de-DE", "Marlene")


def test_resolve_profile_falls_back_to_the_default_language():
    assert resolve_profile(_speech(), "").transcribe_language == "en-US"


def test_resolve_profile_rejects_an_unsupported_language():
    with pytest.raises(UnsupportedLanguageError):
        resolve_profile(_speech(), "fr")


async def test_inmemory_stt_streams_a_single_final_transcript():
    stt = InMemorySttAdapter(_speech())
    frames = [pair async for pair in stt.stream(b"0" * 512)]
    assert frames == [("in-memory transcript", True)]
    assert await stt.transcribe(b"0" * 512) == "in-memory transcript"


async def test_inmemory_stt_yields_nothing_for_empty_audio():
    stt = InMemorySttAdapter(_speech())
    assert [pair async for pair in stt.stream(b"")] == []
    assert await stt.transcribe(b"") == ""


async def test_inmemory_tts_streams_then_synthesizes_the_same_bytes():
    tts = InMemoryTtsAdapter(_speech())
    chunks = [chunk async for chunk in tts.stream("hello")]
    assert b"".join(chunks) == await tts.synthesize("hello") == b"hello"


async def test_inmemory_tts_yields_nothing_for_empty_text():
    tts = InMemoryTtsAdapter(_speech())
    assert [chunk async for chunk in tts.stream("")] == []
    assert await tts.synthesize("") == b""


def test_factory_defaults_to_the_inmemory_adapters():
    settings = Settings()
    assert isinstance(build_stt(settings), InMemorySttAdapter)
    assert isinstance(build_tts(settings), InMemoryTtsAdapter)


def _aws_speech() -> SpeechSettings:
    speech = _speech()
    return speech.model_copy(update={"stt_provider": "aws", "tts_provider": "aws"})


def test_factory_builds_the_aws_adapters_for_the_aws_provider():
    settings = Settings(speech=_aws_speech())
    stt = build_stt(settings, "de")
    tts = build_tts(settings, "de")
    assert isinstance(stt, AwsSttAdapter) and stt._profile.transcribe_language == "de-DE"
    assert isinstance(tts, AwsTtsAdapter) and tts._profile.polly_voice == "Marlene"


def test_factory_aws_provider_rejects_an_unsupported_language():
    settings = Settings(speech=_aws_speech())
    with pytest.raises(UnsupportedLanguageError):
        build_stt(settings, "fr")


def test_factory_aws_provider_falls_back_to_the_default_language():
    settings = Settings(speech=_aws_speech())
    stt = build_stt(settings)
    assert stt._profile.transcribe_language == "en-US"
