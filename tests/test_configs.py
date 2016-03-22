# -*- coding: utf-8 -*-

import pytest

from doctor import Configs


def test_init_with_defaults():
    configs = Configs()

    assert configs['METRICS_ROLLINGSIZE'] == 20
    assert configs['METRICS_ROLLINGSIZE'] == 20

    assert configs['HEALTH_MIN_RECOVERY_TIME'] == 20
    assert configs['HEALTH_MAX_RECOVERY_TIME'] == 2 * 60
    assert configs['HEALTH_THRESHOLD_REQUEST'] == 10
    assert configs['HEALTH_THRESHOLD_TIMEOUT'] == 0.5
    assert configs['HEALTH_THRESHOLD_SYS_EXC'] == 0.5
    assert configs['HEALTH_THRESHOLD_UNKWN_EXC'] == 0.5


def test_setattr():
    configs = Configs()

    configs.METRICS_ROLLINGSIZE = 100
    assert configs['METRICS_ROLLINGSIZE'] == 100

    configs.TEST = 200
    assert 'TEST' not in configs
    with pytest.raises(KeyError):
        configs['TEST']


def test_getattr():
    configs = Configs()

    configs['METRICS_ROLLINGSIZE'] = 100
    assert configs.METRICS_ROLLINGSIZE == 100

    assert 'TEST' not in configs
    assert configs.TEST is None


def test_load():
    configs = Configs()

    configs.load({'METRICS_GRANULARITY': 10})
    assert configs.METRICS_GRANULARITY == 10

    class Settings(object):
        HEALTH_MIN_RECOVERY_TIME = 100
        TEST = 'test'

    configs.load(Settings)
    assert configs.TEST is None
    assert configs.HEALTH_MIN_RECOVERY_TIME == 100
