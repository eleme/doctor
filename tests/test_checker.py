# -*- coding: utf-8 -*-

import time

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


def x(x):
    pass
def y(y):
    pass
def z(z):
    pass
def m(m):
    pass
def n(n):
    pass


def test_requests_all_ok(configs, key):
    """All requests ok, still UNLOCK."""
    tester = HealthTester(configs, m, n, x, y, z)

    for i in range(configs.HEALTH_THRESHOLD_REQUEST + 1):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    assert tester.is_healthy(*key) == True
    assert tester.test(*key) == True
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_UNLOCKED


def test_timeouts_over_threshold(configs, key):
    """timeouts / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, m, n, x, y, z)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_timeout(*key)

    assert tester.is_healthy(*key) == False
    assert tester.test(*key) == False
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED


def test_sys_excs_over_threshold(configs, key):
    """sys_excs / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, m, n, x, y, z)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_sys_exc(*key)

    assert tester.is_healthy(*key) == False
    assert tester.test(*key) == False
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED


def test_unkwn_excs_over_threshold(configs, key):
    """unkwn_excs / requests > THRESHOLD_TIMEOUT, LOCK."""
    tester = HealthTester(configs, m, n, x, y, z)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    for i in range(requests // 2 + 1):
        tester.metrics.on_api_called_unkwn_exc(*key)

    assert tester.is_healthy(*key) == False
    assert tester.test(*key) == False
    assert tester.locks['.'.join(key)]['locked_status'] == MODE_LOCKED


def _set_lock_mode(tester, key, mode):
    lock = tester._get_api_lock('.'.join(key))
    lock['locked_at'] = time.time()
    lock['locked_status'] = mode
    return lock


def test_in_min_recovery_time_health_not_ok(configs, key):
    """In MIN_RECOVERY_TIME, health is not ok, LOCK."""
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_timeout(*key)

    assert tester.is_healthy(*key) == False
    assert tester.test(*key) == False
    assert lock['locked_status'] == MODE_LOCKED


def test_in_min_recovery_time_health_ok(configs, key):
    """Does not locked at least MIN_RECOVERY_TIME, even health is ok,
    still LOCK."""
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    assert tester.is_healthy(*key) == True
    assert tester.test(*key) == False
    assert lock['locked_status'] == MODE_LOCKED


def test_min_recovery_time_passed_health_ok(configs, key):
    """Already locked at least MIN_RECOVERY_TIME, LOCK -> RECOVER."""
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_LOCKED)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
        tester.metrics.on_api_called_ok(*key)

    time.sleep(configs.HEALTH_MIN_RECOVERY_TIME)
    assert tester.is_healthy(*key) == True
    assert tester.test(*key) == True
    assert lock['locked_status'] == MODE_RECOVER


def test_in_max_recovery_time_latest_state_not_ok(configs, key):
    """In MAX_RECOVERY_TIME, latest_state is not ok, RECOVER -> LOCK.
    """
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_sys_exc(*key)

    assert tester.metrics.api_latest_state['.'.join(key)] == False
    assert tester.test(*key) == False
    assert lock['locked_status'] == MODE_LOCKED


def test_in_max_recovery_time_latest_state_ok(configs, key):
    """Does not recover at least MAX_RECOVERY_TIME, even latest state
    is ok, still RECOVER, only random release request."""
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_ok(*key)

    tester.test(*key)
    assert tester.metrics.api_latest_state['.'.join(key)] == True
    assert lock['locked_status'] == MODE_RECOVER


def test_max_recovery_time_passed_latest_state_ok(configs, key):
    """Latest state is ok, and already recovered at least
    MAX_RECOVERY_TIME, RECOVER -> UNLOCK.
    """
    tester = HealthTester(configs, m, n, x, y, z)
    lock = _set_lock_mode(tester, key, MODE_RECOVER)

    requests = configs.HEALTH_THRESHOLD_REQUEST + 1
    for i in range(requests):
        tester.metrics.on_api_called(*key)
    tester.metrics.on_api_called_ok(*key)

    time.sleep(configs.HEALTH_MAX_RECOVERY_TIME)
    assert tester.metrics.api_latest_state['.'.join(key)] == True
    assert tester.test(*key) == True
    assert lock['locked_status'] == MODE_UNLOCKED
