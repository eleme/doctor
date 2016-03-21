# -*- coding: utf-8 -*-

from __future__ import absolute_import

import time
import random
import logging
import functools
from collections import defaultdict


MODE_UNLOCKED = 0
MODE_LOCKED = 1
MODE_RECOVER = 2


class APIHealthTestResult(object):
    """
    ``HealthTester`` result data::

        func            api function to be called.
        service         the service this api belongs to.
        result          the `test` result, (True or False).
        locked_at       the timestamp this api was locked,
                        0 for not locked.
        lock_changed    if status of lock changed, must be MODE_LOCKED
                        or  MODE_UNLOCKED, if not, None.
        health_ok_now   if the api is ok now, True for ok.
        start_at        timestamp when the test starts.
        end_at          timestamp when the test ends.
        logger          service logger
    """
    __slots__ = ['func', 'service', 'result', 'locked_at', 'locked_status',
                 'health_ok_now', 'start_at', 'end_at', 'logger']

    def __init__(self):
        for attr in self.__slots__:
            setattr(self, attr, None)


class HealthTester(object):
    """
    Parameters::

    * metrics: ``Metrics`` object.
    """

    def __init__(self, metrics):
        settings = metrics.configs
        self._metrics = metrics

        self._min_recovery_time = settings.HEALTH_MIN_RECOVERY_TIME
        self._max_recovery_time = settings.HEALTH_MAX_RECOVERY_TIME
        self._threshold_request = settings.HEALTH_THRESHOLD_REQUEST
        self._threshold_timeout = settings.HEALTH_THRESHOLD_TIMEOUT
        self._threshold_sys_exc = settings.HEALTH_THRESHOLD_SYS_EXC
        self._threshold_unkwn_exc = settings.HEALTH_THRESHOLD_UNKWN_EXC

        granularity = settings.METRICS_GRANULARITY
        rollingsize = settings.METRICS_ROLLINGSIZE
        self._interval = granularity * rollingsize

        self._locks = defaultdict(dict)

    @property
    def locks(self):
        """
        `locks` is a dict to hold :meth:`test` runtime data, its schema::

            {func_slug: {locked_at: locked_time,
                        locked_status: status of lock}}

        * locked_at: the time when the fun is locked
        * locked_status: the status of lock
            #. locked:   the func is locked
            #. unlocked: the func is unlocked
            #. recover:  state between locked and unlocked in which the
                         circuit breaker is recovering based on the
                         healthy status of func
        """
        return self._locks

    def test(self, service_name, func_name, logger=None):
        """
        Test current api health before the request is processed, returns
        ``True`` for OK, logic notes:

        * If current api is `unlocked`, lock it until `not is_healthy()`.
        * If current api is `locked`, recover it until `is_healthy()` (and
          locked time span > `MIN_RECOVERY_TIME`), one request will be
          released for health checking once this api enters recover mode.
        * If current api is in `recover` mode, try to unlock it if the latest
          request (the request just released) executed without errors.
          Requests on an api are unlocked gradually, but not immediately. It
          allows more requests to pass as the time becomes longer from the
          time turns to health OK, but it will be unlock anyway when the time
          span is over `MAX_RECOVERY_TIME`. If the latest request failed with
          any errors exccept
          `too_busy_exception`, it will be locked again.
        """
        key = '{0}.{1}'.format(service_name, func_name)

        lock = self._get_api_lock(key)
        locked_at = lock['locked_at']
        locked_status = lock['locked_status']

        health_ok_now = self.is_healthy(service_name, func_name)
        time_now = time.time()

        if not logger:
            logger = logging.getLogger(__name__)
        test_result = APIHealthTestResult()
        test_result.start_at = time_now
        test_result.func_name = func_name
        test_result.service_name = service_name
        test_result.locked_at = locked_at
        test_result.health_ok_now = health_ok_now
        test_result.logger = logger
        test_result.lock_changed = None

        result = None

        if locked_status == MODE_LOCKED:
            if health_ok_now:
                # turns OK
                locked_span = time_now - locked_at
                if locked_span < self._min_recovery_time:
                    # should be locked for at least MIN_RECOVERY_TIME
                    result = False
                else:
                    # enter into recover mode
                    lock['locked_status'] = MODE_RECOVER
                    # release this request for health check
                    result = True
            else:
                result = False
        elif locked_status == MODE_RECOVER:
            if self._metrics.api_latest_state.get(key, False):
                locked_span = time_now - locked_at
                if locked_span >= self._max_recovery_time:
                    lock['locked_at'] = 0
                    lock['locked_status'] = MODE_UNLOCKED
                    test_result.lock_changed = MODE_UNLOCKED
                    result = True
                else:
                    if (random.random() <
                            float(locked_span) / self._max_recovery_time):
                        # allow pass gradually
                        result = True
                    else:
                        # not lucky
                        result = False
            else:
                # still suffering, lock it again
                test_result.locked_at = lock['locked_at'] = time_now
                lock['locked_status'] = MODE_LOCKED
                test_result.lock_changed = MODE_LOCKED
                result = False
        else:
            # not in locked mode now
            if not health_ok_now:
                # turns BAD
                test_result.locked_at = lock['locked_at'] = time_now
                lock['locked_status'] = MODE_LOCKED
                test_result.lock_changed = MODE_LOCKED
                result = False
            else:
                # still OK
                result = True

        test_result.end_at = time.time()
        test_result.result = result
        return test_result

    def _get_api_lock(self, key):
        if key not in self._LOCKS:
            self._locks[key]['locked_at'] = 0
            self._locks[key]['locked_status'] = MODE_UNLOCKED
        return self._LOCKS[key]

    def is_healthy(self, service_name, func_name):
        """
        Check current api health status by metrics, returns `True`
        for status OK::

            if requests > THRESHOLD_REQUEST:
                if timeouts / requests > THRESHOLD_TIMEOUT or
                    sys_excs / requests > THRESHOLD_SYS_EXC:
                    return False
            return True
        """
        key_request = '{0}.{1}'.format(service_name, func_name)
        key_timeout = '{0}.timeout'.format(key_request)
        key_sys_exc = '{0}.sys_exc'.format(key_request)
        key_unkwn_exc = '{0}.unkwn_exc'.format(key_request)

        requests = self._metrics.get(key_request)
        timeouts = self._metrics.get(key_timeout)
        sys_excs = self._metrics.get(key_sys_exc)
        unkwn_exc = self._metrics.get(key_unkwn_exc)

        if requests > self._threshold_request:
            return (((timeouts / float(requests)) < self._threshold_timeout) and
                    ((sys_excs / float(requests)) < self._threshold_sys_exc) and
                    ((unkwn_exc / float(requests)) < self._threshold_unkwn_exc))
        return True


def tester_result_recorder(on_api_health_locked,
                           on_api_health_unlocked,
                           on_api_health_tested,
                           on_api_health_tested_bad,
                           on_api_health_tested_ok):
    """Wraps ``HealthTester().test`` to record ``test_result``,
    the five parameters must be callable and take ``APIHealthTestResult``
    object as argument.
    """
    def _wrapper(func):
        @functools.wraps(func)
        def _record(*args, **kwargs):
            test_result = func(*args, **kwargs)

            if test_result.lock_changed == MODE_LOCKED:
                on_api_health_locked(test_result)
            elif test_result.lock_changed == MODE_UNLOCKED:
                on_api_health_unlocked(test_result)

            on_api_health_tested(test_result)
            if test_result.result:
                on_api_health_tested_ok(test_result)
            else:
                on_api_health_tested_bad(test_result)

            return test_result.result

        return _record
    return _wrapper
