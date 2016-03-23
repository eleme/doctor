## doctor (split from zeus_core/health)

Health is described with current errors percentage, if the health status turns bad, actions like “refuse service” should be taken, mainly to protect our backend databases.

You must invoke `on_*` like methods of `Metrics` to record metrics, then `HealthTester` calculate api call status by thresholds, and based the flowing policy to decide whether the current request can be passed.

### Install

    pip install doctor -i http://pypi.dev.elenet.me/eleme/eleme

### Policy

Current detail policy to test health description:

- if current api is heavily under errors, disallow it to pass the test(), and further incoming requests should be refused ( in at least MIN_RECOVERY_TIME).
- if current api has recoveried from bad health, allow it to pass the test() gradually (via random.random() with priority).

Current errors threholds:

- Errors contains system errors and gevent timeouts.
- Threholds are percentages: errors / requests.
- Errors threholds are checked only if the current requests count is greater than THRESHOLD_REQUEST.

Health check interval:

- Calculated by METRICS_GRANULARITY * METRICS_ROLLINGSIZE, in seconds.

### Settings

```
MIN_RECOVERY_TIME         min recovery time (in seconds)
MAX_RECOVERY_TIME         max recovery time (in seconds)
THRESHOLD_REQUEST         min requests to trigger a health check. (per INTERVAL)  # noqa
THRESHOLD_TIMEOUT         gevent timeout count threshold (per INTERVAL)
THRESHOLD_SYS_EXC         sys_exc count threshold (per INTERVAL)
THRESHOLD_UNKWN_EXC       unkwn_exc count threshold (per INTERVAL)
```

### Examples

```Python
configs = Configs()  # you can custom the settings, see doctor/configs.py
metrics = Metrics(configs)
tester = HealthTester(metrics)


def api_decorator(func):
    @functools.wraps(func)
    def _wrapper(service, *args, **kwargs):
        service_name, func_name = service.name, func.__name__
        test_result = tester.test(service_name, func_name)
        if not test_result.result:
            print('Oh! No!!!')
            return

        result = None
        try:
            result = func(service, *args, **kwargs)
        except UserError:
            metrics.on_api_called_user_exc(service_name, func_name)
        except TimeoutError:
            metrics.on_api_called_timeout(service_name, func_name)
        except SysError:
            metrics.on_api_called_sys_exc(service_name, func_name)
        except Exception:
            metrics.on_api_called_unkwn_exc(service_name, func_name)
        else:
            metrics.on_api_called_ok(service_name, func_name)
        finally:
            metrics.on_api_called(service_name, func_name)

        return result
    return _wrapper


@api_decorator
def api(service):
    client.connect(service.addr)
```

Also you can record test result(`APIHealthTestResult`) by decorator `tester_result_recorder`, for logging(or whatelse):

```Python
def on_api_health_locked(result):
    pass
def on_api_health_unlocked(result):
    pass
def on_api_health_tested(result):
    pass
def on_api_health_tested_bad(result):
    pass
def on_api_health_tested_ok(result):
    pass


recorder = tester_result_recorder(
    on_api_health_locked,
    on_api_health_unlocked,
    on_api_health_tested,
    on_api_health_tested_bad,
    on_api_health_tested_ok
)(tester.test)

# result is not APIHealthTestResult any more, just True or False.
result = recoder(service_name, func_name)
```

### Ports

- [Go](https://github.com/eleme/circuitbreaker)

### Authors

* @Damnever
* @xiangyu.wang
* @hit9
