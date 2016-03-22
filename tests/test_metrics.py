# -*- coding: utf-8 -*-

import time

from doctor.metrics import RollingNumber, Metrics


def test_rollingnumber():
    rn = RollingNumber(2, 1)

    rn.incr(1)
    assert rn._values == [0, 1]
    rn.incr(2)
    assert rn._values == [0, 3]

    time.sleep(1)
    rn.incr(1)
    assert rn._values == [3, 1]
    rn.incr(3)
    assert rn._values == [3, 4]

    time.sleep(2)
    assert rn.value() == 0


def test_metrics():
    metrics = Metrics()

    metrics.incr('foo.bar', 1)
    assert metrics.get('foo.bar') == 1

    metrics.on_api_called('foo', 'bar')
    assert metrics.get('foo.bar') == 2

    metrics.on_api_called_ok('bar', 'foo')
    assert metrics.api_latest_state['bar.foo'] == True

    metrics.on_api_called_user_exc('foo', 'baz')
    assert metrics.api_latest_state['foo.baz'] == True

    metrics.on_api_called_timeout('bar', 'baz')
    assert metrics.get('bar.baz.timeout') == 1

    metrics.on_api_called_sys_exc('baz', 'foo')
    assert metrics.get('baz.foo.sys_exc') == 1
    assert metrics.api_latest_state['baz.foo'] == False
