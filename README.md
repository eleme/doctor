## doctor

Health is described with current errors percentage, if the health status turns bad, actions like “refuse service” should be taken, mainly to protect our backend databases.

You must invoke `on_*` like methods of `doctor.checker.HealthTester.metrics`(`doctor.metrics.Metrics`) to record metrics, then `HealthTester.is_healthy` calculate api call status by thresholds, and `HealthTester.test` based the flowing policy to decide whether the current request can be passed.

### Install

    pip install git+https://github.com/eleme/doctor.git

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
# callbacks, take *doctor.checker.APIHealthTestCtx* as arguments
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

# you can custom the settings, see doctor/configs.py
configs = Configs()

# callbacks order matters.
tester = HealthTester(
    configs,
    on_api_health_locked,
    on_api_health_unlocked,
    on_api_health_tested,
    on_api_health_tested_bad,
    on_api_health_tested_ok,
)


def api_decorator(func):
    @functools.wraps(func)
    def _wrapper(service, *args, **kwargs):
        service_name, func_name = service.name, func.__name__
        if not tester.test(service_name, func_name):
            print('Oh! No!!!')
            return

        result = None
        try:
            result = func(service, *args, **kwargs)
        except UserError:
            tester.metrics.on_api_called_user_exc(service_name, func_name)
        except TimeoutError:
            tester.metrics.on_api_called_timeout(service_name, func_name)
        except SysError:
            tester.metrics.on_api_called_sys_exc(service_name, func_name)
        except Exception:
            tester.metrics.on_api_called_unkwn_exc(service_name, func_name)
        else:
            tester.metrics.on_api_called_ok(service_name, func_name)
        finally:
            tester.metrics.on_api_called(service_name, func_name)

        return result
    return _wrapper


@api_decorator
def api(service):
    client.connect(service.addr)
```

### Ports

- [Go](https://github.com/eleme/circuitbreaker)

### Authors

* @Damnever
* @xiangyu.wang
* @hit9
