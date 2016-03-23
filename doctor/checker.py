# -*- coding: utf-8 -*-

from __future__ import absolute_import

import time
import random
import logging
from collections import defaultdict

from .metrics import Metrics


MODE_UNLOCKED = 0
MODE_LOCKED = 1
MODE_RECOVER = 2


class APIHealthTestCtx(object):
    """
    `API call` context to hold data::

        func            api function to be called.
        service         the service this api belongs to.
        result          the `test` result, (True or False).
        lock            current api lock information, dict,
                        keys: ``locked_at``, ``locked_status``.
        health_ok_now   if the api is ok now, True for ok.
        start_at        timestamp when the test starts.
        end_at          timestamp when the test ends.
        logger          service logger
    """
    __slots__ = ['func_name', 'service_name', 'result', 'lock',
                 'health_ok_now', 'start_at', 'end_at', 'logger']

    def __init__(self):
        for attr in self.__slots__:
            setattr(self, attr, None)


class HealthTester(object):
    """
    Parameters::

    * configs: ``Configs`` object.
    """

    def __init__(self, configs,
                 on_api_health_locked,
                 on_api_health_unlocked,
                 on_api_health_tested,
                 on_api_health_tested_bad,
                 on_api_health_tested_ok):
        self._metrics = Metrics(configs)

        # init settings
        self._min_recovery_time = configs.HEALTH_MIN_RECOVERY_TIME
        self._max_recovery_time = configs.HEALTH_MAX_RECOVERY_TIME
        self._threshold_request = configs.HEALTH_THRESHOLD_REQUEST
        self._threshold_timeout = configs.HEALTH_THRESHOLD_TIMEOUT
        self._threshold_sys_exc = configs.HEALTH_THRESHOLD_SYS_EXC
        self._threshold_unkwn_exc = configs.HEALTH_THRESHOLD_UNKWN_EXC

        granularity = configs.METRICS_GRANULARITY
        rollingsize = configs.METRICS_ROLLINGSIZE
        self._interval = granularity * rollingsize

        # callbacks
        self._on_api_health_locked = on_api_health_locked
        self._on_api_health_unlocked = on_api_health_unlocked
        self._on_api_health_tested = on_api_health_tested
        self._on_api_health_tested_bad = on_api_health_tested_bad
        self._on_api_health_tested_ok = on_api_health_tested_ok

        self._locks = defaultdict(dict)

    @property
    def metrics(self):
        """``Metrics`` object."""
        return self._metrics

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
        ctx = APIHealthTestCtx()
        ctx.start_at = time_now
        ctx.func_name = func_name
        ctx.service_name = service_name
        ctx.health_ok_now = health_ok_now
        ctx.logger = logger

        lock_changed = None
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
                    lock_changed = MODE_RECOVER
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
                    lock_changed = MODE_UNLOCKED
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
                lock['locked_at'] = time_now
                lock['locked_status'] = MODE_LOCKED
                lock_changed = MODE_LOCKED
                result = False
        else:
            # not in locked mode now
            if not health_ok_now:
                # turns BAD
                lock['locked_at'] = time_now
                lock['locked_status'] = MODE_LOCKED
                lock_changed = MODE_LOCKED
                result = False
            else:
                # still OK
                result = True

        ctx.end_at = time.time()
        ctx.result = result
        ctx.lock = lock.copy()
        # call callbacks.
        if lock_changed == MODE_LOCKED:
            self._on_api_health_locked(ctx)
        elif lock_changed == MODE_UNLOCKED:
            self._on_api_health_unlocked(ctx)

        self._on_api_health_tested(ctx)
        if result:
            self._on_api_health_tested_ok(ctx)
        else:
            self._on_api_health_tested_bad(ctx)
        return result

    def _get_api_lock(self, key):
        if key not in self._locks:
            self._locks[key]['locked_at'] = 0
            self._locks[key]['locked_status'] = MODE_UNLOCKED
        return self._locks[key]

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
