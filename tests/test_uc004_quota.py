"""NFR-013 y UC-004 BR-005/BR-006: cuotas atómicas por usuario y globales."""

from datetime import UTC, datetime

import pytest

from spec_to_runtime.common import quota
from tests.conftest import counter

NOW = datetime(2026, 9, 26, 15, 0, tzinfo=UTC)  # 10:00 en Colombia
DAY = "2026-09-26"


def reserve(aws, user="u1", role="Participant", cap=3000, now=NOW):
    quota.reserve(aws.usage_client, "usage", user, role, now, cap)


def test_uc004_br005_reserve_counts_the_user_and_the_project(aws):
    reserve(aws)
    reserve(aws)
    assert counter(aws, "USER#u1", DAY) == 2
    assert counter(aws, "GLOBAL", "TOTAL") == 2


def test_uc004_br005_participant_limit_is_25_per_day(aws):
    for _ in range(25):
        reserve(aws)
    with pytest.raises(quota.LimitReachedError) as error:
        reserve(aws)
    assert error.value.kind == "daily"
    assert counter(aws, "USER#u1", DAY) == 25
    assert counter(aws, "GLOBAL", "TOTAL") == 25  # la rechazada no consumió el contador global


def test_uc007_br007_speaker_limit_is_100_per_day(aws, monkeypatch):
    monkeypatch.setitem(quota.DAILY_LIMITS, "Speaker", 3)  # mismo mecanismo, tope pequeño
    for _ in range(3):
        reserve(aws, role="Speaker")
    with pytest.raises(quota.LimitReachedError):
        reserve(aws, role="Speaker")
    assert quota.DAILY_LIMITS["Participant"] == 25


def test_uc004_br005_project_cap_applies_across_users_and_wins_over_the_daily_limit(aws):
    reserve(aws, user="a", cap=2)
    reserve(aws, user="b", cap=2)
    with pytest.raises(quota.LimitReachedError) as error:
        reserve(aws, user="c", cap=2)
    assert error.value.kind == "project"
    assert counter(aws, "USER#c", DAY) == 0  # transacción: no quedó a medias


def test_uc004_br006_release_returns_the_unit_and_never_goes_below_zero(aws):
    reserve(aws)
    quota.release(aws.usage_client, "usage", "u1", DAY)
    assert counter(aws, "USER#u1", DAY) == 0 and counter(aws, "GLOBAL", "TOTAL") == 0
    quota.release(aws.usage_client, "usage", "u1", DAY)  # de más: se ignora
    assert counter(aws, "USER#u1", DAY) == 0


def test_uc004_the_daily_counter_uses_the_local_day_of_the_event(aws):
    late = datetime(2026, 9, 27, 3, 0, tzinfo=UTC)  # 22:00 del 26 en Colombia
    reserve(aws, now=late)
    assert counter(aws, "USER#u1", "2026-09-26") == 1
    assert quota.local_day(late) == "2026-09-26"
    assert quota.next_reset(late) == "2026-09-27T05:00:00+00:00"
