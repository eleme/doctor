# -*- coding: utf-8 -*-

import time

from doctor import HealthTester, Metrics, Configs
from doctor.checker import MODE_LOCKED, MODE_UNLOCKED


def test_health_tester():
    configs = Configs()
    configs.HEALTH_THRESHOLD_REQUEST = 9
    configs.HEALTH_MIN_RECOVERY_TIME = 2
    configs.HEALTH_MAX_RECOVERY_TIME = 4
    metrics = Metrics(configs)
    tester = HealthTester(metrics)

    key = ('hello', 'world')

    for i in range(10):
        metrics.on_api_called(*key)
    metrics.on_api_called_ok(*key)

    test_result = tester.test(*key)
    assert test_result.result == True
    assert test_result.lock_changed is None

    # UNLOCK -> LOCK
    for i in range(5):
        metrics.on_api_called_timeout(*key)

    test_result = tester.test(*key)
    assert test_result.result == False
    assert test_result.lock_changed == MODE_LOCKED

    # health not ok, still LOCK
    for i in range(10):
        metrics.on_api_called(*key)
    for i in range(10):
        metrics.on_api_called_unkwn_exc(*key)

    test_result = tester.test(*key)
    assert test_result.result == False
    assert test_result.lock_changed is None

    # does not locked for at least MIN_RECOVERY_TIME, still LOCK
    for i in range(10):
        metrics.on_api_called(*key)
    test_result = tester.test(*key)
    assert test_result.result == False
    assert test_result.lock_changed is None

    # already locked at least MIN_RECOVERY_TIME, LOCK -> RECOVER
    time.sleep(configs.HEALTH_MIN_RECOVERY_TIME)

    test_result = tester.test(*key)
    assert test_result.result == True
    assert test_result.lock_changed is None

    # random release request
    metrics.on_api_called_ok(*key)

    test_result = tester.test(*key)
    assert test_result.lock_changed is None

    # HEALTH_MAX_RECOVERY_TIME passed, RECOVER -> UNLOCK
    time.sleep(configs.HEALTH_MAX_RECOVERY_TIME -
               configs.HEALTH_MIN_RECOVERY_TIME)
    test_result = tester.test(*key)
    assert test_result.result == True
    assert test_result.lock_changed == MODE_UNLOCKED

    # api_latest_state == False, RECOVER -> LOCK
    # last situation, pass.
