#!/usr/bin/env python
import asyncio
from functools import partial
import logging
import time

import omero.clients
from omero.rtypes import unwrap


def _firstline_truncate(s):
    lines = "{}\n".format(s).splitlines()
    if len(lines[0]) > 80 or len(lines) > 1:
        s = lines[0][:79] + "…"
    return s


async def _exec_ice_async(future, func, *args, **kwargs):

    # Ice runs in a different thread from asyncio so must use
    # call_soon_threadsafe
    # https://docs.python.org/3.6/library/asyncio-dev.html#concurrency-and-multithreading

    def exception_cb(ex):
        logging.warning("exception_cb: %s", _firstline_truncate(ex))
        future.get_loop().call_soon_threadsafe(future.set_exception, ex)

    def response_cb(result):
        logging.info("response_cb: %s", _firstline_truncate(result))
        future.get_loop().call_soon_threadsafe(future.set_result, result)

    a = func(*args, **kwargs, _response=response_cb, _ex=exception_cb)
    logging.debug(
        "_exec_ice_async(%s) sent:%s completed:%s",
        func.__name__,
        a.isSent(),
        a.isCompleted(),
    )


async def ice_async(func, *args, **kwargs):
    # https://docs.python.org/3.6/library/asyncio-task.html#example-future-with-run-until-complete
    future = asyncio.Future()
    asyncio.ensure_future(_exec_ice_async(future, func, *args, **kwargs))
    result = await future
    return result


class AsyncService:
    def __init__(self, svc):
        def copy_doc(a, b):
            setattr(b, "__doc__", getattr(a, "__doc__"))

        methods = {
            m for m in dir(svc) if callable(getattr(svc, m)) and not m.startswith("_")
        }
        async_methods = {m for m in methods if m.startswith("begin_")}
        for async_m in async_methods:
            m = async_m[6:]
            methods.remove(m)
            methods.remove("begin_" + m)
            methods.remove("end_" + m)
            setattr(self, m, partial(ice_async, getattr(svc, async_m)))
            copy_doc(getattr(svc, async_m), getattr(self, m))
        for sync_m in methods:
            setattr(self, sync_m, partial(getattr(svc, sync_m)))
            copy_doc(getattr(svc, sync_m), getattr(self, sync_m))


async def do_stuff(session, serial):
    acs = AsyncService(session.getConfigService())
    aqs = AsyncService(session.getQueryService())
    coroutines = [
        acs.getClientConfigDefaults(),
        aqs.projection("SELECT id FROM Screen", None),
        aqs.projection("SELECT id FROM Project", None),
        aqs.projection("SELECT name FROM Screen", None),
        aqs.projection("SELECT name FROM Project", None),
        aqs.projection("SELECT description FROM Screen", None),
        aqs.projection("SELECT description FROM Project", None),
        aqs.projection("SELECT details.owner.omeName FROM Screen", None),
        aqs.projection("SELECT details.owner.omeName FROM Project", None),
        aqs.projection("SELECT details.group.name FROM Screen", None),
        aqs.projection("SELECT details.group.name FROM Project", None),
    ]
    if serial:
        for coro in coroutines:
            r = await coro
            print(unwrap(r))
    else:
        rs = await asyncio.gather(*coroutines)
        for r in rs:
            print(unwrap(r))


logging.basicConfig(level=logging.DEBUG)
# True: Run one query at a time, False: run concurrently
serial = False
# serial = True
client = omero.client("idr.openmicroscopy.org")
session = client.createSession("public", "public")
try:
    # asyncio.run(do_stuff(session))

    # https://docs.python.org/3.6/library/asyncio-dev.html
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    start = time.perf_counter()
    loop.run_until_complete(do_stuff(session, serial))
    end = time.perf_counter() - start
    print(f"Time taken for queries: {end:0.2f} seconds.")
finally:
    client.closeSession()
