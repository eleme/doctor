# -*- coding: utf-8 -*-

import logging
from .. import HealthTester, Configs

logger = logging.getLogger(__name__)


EXPORTED_CALLBACKS = [
    "on_api_health_locked",
    "on_api_health_unlocked",
    "on_api_health_tested",
    "on_api_health_tested_bad",
    "on_api_health_tested_ok",
    ]

class Doctor(object):
    def __init__(self, failure_exception, settings=None):
        self.configs = Configs(settings)
        self.app = None
        self.tester = None
        self.failure_exception = failure_exception

    def test(self, app_meta):
        app, func_name = app_meta.app, app_meta.name
        if not self.tester.test(app.service_name, func_name):
            raise self.failure_exception

    def init_app(self, app):
        if self.app is not None:
            raise RuntimeError("Plugin is alread registered")
        self.tester = HealthTester(
            self.configs,
            self.on_api_health_locked,
            self.on_api_health_unlocked,
            self.on_api_health_tested,
            self.on_api_health_tested_bad,
            self.on_api_health_tested_ok,
            )
        self.app = app
        self.app.before_api_call(self.test)
        self.app.tear_down_api_call(self.collect_api_call_result)

    def collect_api_call_result(self, api_meta, result_meta):
        service_name, func_name = api_meta.app.service_name, api_meta.name
        self.tester.metrics.on_api_called(service_name, func_name)
        if result_meta.error is None:
            self.tester.metrics.on_api_called_ok(service_name, func_name)
        else:
            self.tester.metrics.on_api_called_unkwn_exc(service_name,
                                                        func_name)


    def set_handler(self, name, func):
        if name not in EXPORTED_CALLBACKS:
            raise RuntimeError("name should be only in %r", EXPORTED_CALLBACKS)
        setattr(self, name, func)

    def on_api_health_locked(self, result):
        pass

    def on_api_health_unlocked(self, result):
        pass

    def on_api_health_tested(self, result):
        pass

    def on_api_health_tested_bad(self, result):
        pass

    def on_api_health_tested_ok(self, result):
        pass
