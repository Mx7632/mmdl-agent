import asyncio
import inspect


def pytest_pyfunc_call(pyfuncitem):
    test_function = pyfuncitem.obj
    if inspect.iscoroutinefunction(test_function):
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            kwargs = {
                name: pyfuncitem.funcargs[name]
                for name in inspect.signature(test_function).parameters
                if name in pyfuncitem.funcargs
            }
            loop.run_until_complete(test_function(**kwargs))
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return True
    return None
