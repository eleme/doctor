# -*- coding: utf-8 -*-

from __future__ import print_function, division, absolute_import

"""
Metrics
=======

In process metrics.

Features
---------

1. Behaves like a statsd client, but in process.
2. Currently only support counters.
3. Counters are implemented in ``RollingNumber``, a rolling number
   is like a sliding window on timestamp sequence.

Settings
--------
::

    METRICS_GRANULARITY:              stats time granularity. (in seconds)
    METRICS_ROLLINGSIZE:              rolling number's window length.

Methods
--------
::

    get(key, default=0)     get current counter value by ``key``, if the key
                            was not found, gives ``default``.
    incr(key, value=1)      increment the counter value by ``value``, if the
                            counter was not found, create one and increment it.

Apis
----
"""

import time

from .configs import Configs


class RollingNumber(object):
    """
    RollingNumber behaves like a FIFO queue with fixed length, or a
    sliding window on timestamp sequence::

        1 2 0 3 [4 5 1 2 4 2] 3 4 ...   (<= time passing)
                +--- 18  ---+

    A rolling number's value is the ``sum`` of the queue elements, the
    last element's value will roll into previous position once the clock
    passed 1 ``granularity`` (default ``1s``).

    Rolling number dosen't use an event loop (i.e. via gevent) to roll elements
    on time goes on, it uses passive clock checking instead. All read/write
    actions like ``incr()``, ``value()`` will shift current rolling number to
    align its internel ``_clock`` with timestamp now. The shift will pop
    elements on the left and fill ``0`` on the right, so if there is a long
    time no data incoming, the rolling number will change to a all zero queue.
    (aka, with its value as ``0``).

    Attributes:
      rolling_size           the sliding window length
      rolling_granularity    the shifting timestamp granularity (default: 1s)
    """

    def __init__(self, rolling_size, rolling_granularity=1):
        """
        Init a rolling number to 0 with size.
        """
        self.rolling_size = rolling_size
        self.rolling_granularity = rolling_granularity

        self._clock = time.time()
        self._values = [0] * rolling_size

    def clear(self):
        """
        Clear the value to all zeros.

        *Note*: :meth:`clear` dosen't shift the `clock`, it will certainly
        set the rolling number to zero.
        """
        self._values = [0] * self.rolling_size

    def value(self):
        """
        Return the value this rolling number present, actually the ``sum()``
        value of this queue.
        """
        self.shift_on_clock_changes()
        return sum(self._values)

    __int__ = value

    def increment(self, value):
        """
        Increment this number by `value`, will increment the last element by ``
        value``.
        """
        self.shift_on_clock_changes()
        self._values[-1] += value

    incr = increment

    def shift(self, length):
        """
        Shift the rolling number to the right by ``length``, will pop elements
        on the left and fill ``0`` on the right.
        """
        if length <= 0:
            return

        if length > self.rolling_size:
            return self.clear()

        end = [0] * length
        self._values = self._values[length:] + end

    def shift_on_clock_changes(self):
        """
        Shift the rolling number if its ``_clock`` is bebind the timestamp
        ``now`` by at least 1 timestamp granularity, and synchronous its
        ``_clock`` to ``now``.
        """
        now = time.time()
        length = int((now - self._clock) / self.rolling_granularity)
        if length > 0:
            self.shift(length)
            self._clock = now

    def __repr__(self):
        """
        Python presentation: `<rolling number %v [...]>`
        """
        return '<rolling number {0} {1}>'.format(self.value(), self._values)


class Metrics(object):

    def __init__(self, settings=None):
        if settings is None:
            settings = Configs()
        self._granularity = settings.METRICS_GRANULARITY
        self._rollingsize = settings.METRICS_ROLLINGSIZE

        self._api_latest_state = dict()
        self._counters = dict()

    @property
    def counters(self):
        return self._counters

    @property
    def api_latest_state(self):
        """
        A dict to record the latest api call result, schema: `{api_name: True/False}`.
        If the latest call on this api succeeds without any errors (except the
        `too_busy_exception`), the value in this dict will be set to be `True`, else
        `False`.
        """
        return self._api_latest_state

    def incr(self, key, value=1):
        """Increment counter by `value`."""
        if key not in self._counters:
            self._counters[key] = RollingNumber(
                self._rollingsize, rolling_granularity=self._granularity)
        counter = self._counters[key]
        counter.incr(value)

    def get(self, key, default=0):
        """Get metric value by `key`."""
        v = self._counters.get(key, None)
        return (v and v.value()) or default

    def on_api_called(self, service_name, func_name):
        self.incr('{0}.{1}'.format(service_name, func_name))

    def on_api_called_ok(self, service_name, func_name):
        self._api_latest_state['{0}.{1}'.format(service_name,
                                                func_name)] = True

    def on_api_called_user_exc(self, service_name, func_name):
        self._api_latest_state['{0}.{1}'.format(service_name,
                                                func_name)] = True

    def on_api_called_timeout(self, service_name, func_name):
        self.incr('{0}.{1}.timeout'.format(service_name, func_name))

    def on_api_called_sys_exc(self, service_name, func_name):
        self.incr('{0}.{1}.sys_exc'.format(service_name, func_name))
        self._api_latest_state['{0}.{1}'.format(service_name,
                                                func_name)] = False

    def on_api_called_unkwn_exc(self, service_name, func_name):
        self.incr('{0}.{1}.unkwn_exc'.format(service_name, func_name))
        self._api_latest_state['{0}.{1}'.format(service_name,
                                                func_name)] = False
