# -*- coding = utf-8 -*-

from __future__ import absolute_import


class Configs(dict):
    """
    Configs for ``Metrics`` and ``HealthTester``.
    """

    def __init__(self, settings=None):
        defaults = dict(
            # Metrics settings.
            METRICS_GRANULARITY=20,  # sec
            METRICS_ROLLINGSIZE=20,
            # Health settings.
            HEALTH_MIN_RECOVERY_TIME=20,  # sec
            HEALTH_MAX_RECOVERY_TIME=2 * 60,  # sec
            HEALTH_THRESHOLD_REQUEST=10 * 1,  # per `INTERVAL`
            HEALTH_THRESHOLD_TIMEOUT=0.5,  # percentage per `INTERVAL`
            HEALTH_THRESHOLD_SYS_EXC=0.5,  # percentage per `INTERVAL`
            HEALTH_THRESHOLD_UNKWN_EXC=0.5,  # percentage per `INTERVAL`
        )
        super(self.__class__, self).__init__(**defaults)

        if settings is not None:
            self.load(settings)

    def load(self, obj):
        if isinstance(obj, dict):
            items = obj.iteritems()
        else:
            items = obj.__dict__.iteritems()

        for k, v in items:
            if k in self:
                self[k] = v

    def __setattr__(self, k, v):
        if k in self:
            self[k] = v

    def __getattr__(self, k):
        return super(self.__class__, self).get(k, None)
