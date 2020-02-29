#!/usr/bin/env python
import asyncio
import logging
import time

import omero.clients
from omero.rtypes import unwrap


async def _exec_ice_async(future, func, *args, **kwargs):
    def exception_cb(ex):
        print("exception_cb", str(ex)[:40])
        future.get_loop().call_soon_threadsafe(future.set_exception, ex)

    def response_cb(result):
        print("response_cb", str(result)[:40])
        # Ice runs in a different thread that asyncio doesn't know about
        # https://docs.python.org/3.6/library/asyncio-dev.html#concurrency-and-multithreading
        future.get_loop().call_soon_threadsafe(future.set_result, result)

    a = func(*args, **kwargs, _response=response_cb, _ex=exception_cb)
    print("_exec_ice_async", a, a.isCompleted())
    # await asyncio.sleep(1)
    # exception_cb(Exception('ice_async'))
    # response_cb('ice_async')


async def ice_async(func, *args, **kwargs):
    # https://docs.python.org/3.6/library/asyncio-task.html#example-future-with-run-until-complete
    future = asyncio.Future()
    asyncio.ensure_future(_exec_ice_async(future, func, *args, **kwargs))
    result = await future
    return result


async def do_stuff(session, serial):
    cs = session.getConfigService()
    qs = session.getQueryService()
    coroutines = [
        ice_async(cs.begin_getClientConfigDefaults),
        ice_async(qs.begin_projection, "SELECT id FROM Screen", None),
        ice_async(qs.begin_projection, "SELECT id FROM Project", None),
        ice_async(qs.begin_projection, "SELECT name FROM Screen", None),
        ice_async(qs.begin_projection, "SELECT name FROM Project", None),
        ice_async(qs.begin_projection, "SELECT description FROM Screen", None),
        ice_async(qs.begin_projection, "SELECT description FROM Project", None),
        ice_async(
            qs.begin_projection, "SELECT details.owner.omeName FROM Screen", None
        ),
        ice_async(
            qs.begin_projection, "SELECT details.owner.omeName FROM Project", None
        ),
        ice_async(qs.begin_projection, "SELECT details.group.name FROM Screen", None),
        ice_async(qs.begin_projection, "SELECT details.group.name FROM Project", None),
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
serial = True
client = omero.client("idr.openmicroscopy.org")
session = client.createSession("public", "public")
try:
    start = time.perf_counter()
    # asyncio.run(do_stuff(session))

    # https://docs.python.org/3.6/library/asyncio-dev.html
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    loop.run_until_complete(do_stuff(session, serial))
    end = time.perf_counter() - start
    print(f"Time taken for queries: {end:0.2f} seconds.")
finally:
    client.closeSession()
