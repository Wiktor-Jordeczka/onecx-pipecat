import pytest

from onecx_pipecat.config import AwsSpeechProfile, SpeechSettings
from onecx_pipecat.services.inmemory import InMemorySTT, InMemoryTTS
from onecx_pipecat.services.speech import (
    UnsupportedLanguageError,
    build_stt_service,
    build_tts_service,
    resolve_profile,
)


def _speech(**overrides) -> SpeechSettings:
    return SpeechSettings(
        region="eu-west-1",
        default_language="en",
        aws_profiles={
            "en": AwsSpeechProfile(transcribe_language="en-US", polly_voice="Joanna"),
            "de": AwsSpeechProfile(transcribe_language="de-DE", polly_voice="Marlene"),
        },
        **overrides,
    )


def test_resolve_profile_maps_the_pinned_language():
    profile = resolve_profile(_speech(), "de")
    assert (profile.transcribe_language, profile.polly_voice) == ("de-DE", "Marlene")


def test_resolve_profile_falls_back_to_the_default_language():
    assert resolve_profile(_speech(), "").transcribe_language == "en-US"


def test_resolve_profile_rejects_an_unsupported_language():
    with pytest.raises(UnsupportedLanguageError):
        resolve_profile(_speech(), "fr")


def test_default_provider_builds_the_inmemory_services():
    from onecx_pipecat.config import Settings

    settings = Settings()
    assert isinstance(build_stt_service(settings, "en"), InMemorySTT)
    assert isinstance(build_tts_service(settings, "en"), InMemoryTTS)


def test_aws_provider_rejects_an_unsupported_language():
    from onecx_pipecat.config import Settings

    settings = Settings(speech=_speech(stt_provider="aws", tts_provider="aws"))
    with pytest.raises(UnsupportedLanguageError):
        build_stt_service(settings, "fr")
    with pytest.raises(UnsupportedLanguageError):
        build_tts_service(settings, "fr")


def test_aws_provider_builds_pipecat_services_for_the_pinned_language():
    from pipecat.services.aws.stt import AWSTranscribeSTTService
    from pipecat.services.aws.tts import AWSPollyTTSService

    from onecx_pipecat.config import Settings

    settings = Settings(speech=_speech(stt_provider="aws", tts_provider="aws"))
    assert isinstance(build_stt_service(settings, "de"), AWSTranscribeSTTService)
    assert isinstance(build_tts_service(settings, "de"), AWSPollyTTSService)
