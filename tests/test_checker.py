# -*- coding: utf-8 -*-

import time

import mock
import pytest

from doctor import HealthTester, Configs
from doctor.checker import MODE_LOCKED, MODE_UNLOCKED, MODE_RECOVER


@pytest.fixture(scope='function')
def configs():
    configs = Configs()
    configs.HEALTH_THRESHOLD_REQUEST = 9
    configs.HEALTH_MIN_RECOVERY_TIME = 1
    configs.HEALTH_MAX_RECOVERY_TIME = 1
    return configs

@pytest.fixture(scope='function')
def key():
    return ('hello', 'world')

@pytest.fixture(scope='function')
def f_locked():
    return mock.Mock()

@pytest.fixture(scope='function')
def f_unlocked():
    return mock.Mock()

@pytest.fixture(scope='function')
def f_tested():
    return mock.Mock()

@pytest.fixture(scope='function')
def f_tested_bad():
    return mock.Mock()

@pytest.fixture(scope='function')
def f_tested_ok():
    return mock.Mock()


def test_non_callbacks(configs):
    HealthTester(configs)._send_test_call_ctx(None, None, None)


def test_requests_all_ok(configs, key, f_locked, f_unlocked,
                         f_tested, f_tested_bad, f_tested_ok):
    """All requests ok, still UNLOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)

    for i in range(configs.HEALTH_THRESHOLD_REQUEST + 1):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    assert tester.is_healthy(*key)
    assert tester.test(*key)
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_UNLOCKED
    assert not f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert f_tested_ok.called
    assert not f_tested_bad.called


def test_timeouts_over_threshold(configs, key, f_locked, f_unlocked,
                                 f_tested, f_tested_bad, f_tested_ok):
    """timeouts / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_timeout(*key)

    assert not tester.is_healthy(*key)
    assert not tester.test(*key)
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED
    assert f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def test_sys_excs_over_threshold(configs, key, f_locked, f_unlocked,
                                 f_tested, f_tested_bad, f_tested_ok):
    """sys_excs / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_sys_exc(*key)

    assert not tester.is_healthy(*key)
    assert not tester.test(*key)
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED
    assert f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def test_unkwn_excs_over_threshold(configs, key, f_locked, f_unlocked,
                                   f_tested, f_tested_bad, f_tested_ok):
    """unkwn_excs / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_unkwn_exc(*key)

    assert not tester.is_healthy(*key)
    assert not tester.test(*key)
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED
    assert f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def _set_lock_mode(tester, key, mode):
    lock = tester._get_api_lock('.'.join(key))
    lock['locked_at'] = time.time()
    lock['locked_status'] = mode
    return lock


def test_in_min_recovery_time_health_not_ok(configs, key,
                                            f_locked, f_unlocked,
                                            f_tested, f_tested_bad,
                                            f_tested_ok):
    """In MIN_RECOVERY_TIME, health is not ok, still LOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_timeout(*key)

    assert not tester.is_healthy(*key)
    assert not tester.test(*key)
    assert lock['locked_status'] == MODE_LOCKED
    assert not f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def test_in_min_recovery_time_health_ok(configs, key,
                                        f_locked, f_unlocked,
                                        f_tested, f_tested_bad,
                                        f_tested_ok):
    """Does not locked at least MIN_RECOVERY_TIME, even health is ok,
    still LOCK."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    assert tester.is_healthy(*key)
    assert not tester.test(*key)
    assert lock['locked_status'] == MODE_LOCKED
    assert not f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def test_min_recovery_time_passed_health_ok(configs, key,
                                            f_locked, f_unlocked,
                                            f_tested, f_tested_bad,
                                            f_tested_ok):
    """Already locked at least MIN_RECOVERY_TIME, LOCK -> RECOVER."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    time.sleep(configs.HEALTH_MIN_RECOVERY_TIME)
    assert tester.is_healthy(*key)
    assert tester.test(*key)
    assert lock['locked_status'] == MODE_RECOVER
    assert not f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert f_tested_ok.called
    assert not f_tested_bad.called


def test_in_max_recovery_time_latest_state_not_ok(configs, key,
                                                  f_locked, f_unlocked,
                                                  f_tested, f_tested_bad,
                                                  f_tested_ok):
    """In MAX_RECOVERY_TIME, latest_state is not ok, RECOVER -> LOCK.
    """
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_sys_exc(*key)

    assert not tester.metrics.api_latest_state['.'.join(key)]
    assert not tester.test(*key)
    assert lock['locked_status'] == MODE_LOCKED
    assert f_locked.called
    assert not f_unlocked.called
    assert f_tested.called
    assert not f_tested_ok.called
    assert f_tested_bad.called


def test_in_max_recovery_time_latest_state_ok(configs, key,
                                              f_locked, f_unlocked,
                                              f_tested, f_tested_bad,
                                              f_tested_ok):
    """Does not recover at least MAX_RECOVERY_TIME, even latest state
    is ok, still RECOVER, only random release request."""
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_ok(*key)

    tester.test(*key)
    assert tester.metrics.api_latest_state['.'.join(key)]
    assert lock['locked_status'] == MODE_RECOVER
    assert not f_locked.called
    assert not f_unlocked.called
    assert f_tested.called


def test_max_recovery_time_passed_latest_state_ok(configs, key,
                                                  f_locked, f_unlocked,
                                                  f_tested, f_tested_bad,
                                                  f_tested_ok):
    """Latest state is ok, and already recovered at least
    MAX_RECOVERY_TIME, RECOVER -> UNLOCK.
    """
    tester = HealthTester(configs, f_locked, f_unlocked,
                          f_tested, f_tested_bad, f_tested_ok)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_ok(*key)

    time.sleep(configs.HEALTH_MAX_RECOVERY_TIME)
    assert tester.metrics.api_latest_state['.'.join(key)]
    assert tester.test(*key)
    assert lock['locked_status'] == MODE_UNLOCKED
    assert not f_locked.called
    assert f_unlocked.called
    assert f_tested.called
    assert f_tested_ok.called
    assert not f_tested_bad.called
