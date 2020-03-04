#!/usr/bin/env python
from omero_asyncio import AsyncClient
import asyncio
import logging
import time

# import omero.clients
from omero.rtypes import unwrap

HOST = "idr.openmicroscopy.org"
USER = "public"
PASSWORD = "public"


async def do_stuff(configsvc, querysvc, serial):
    coroutines = [
        configsvc.getClientConfigDefaults(),
        querysvc.projection("SELECT id FROM Screen", None),
        querysvc.projection("SELECT id FROM Project", None),
        querysvc.projection("SELECT name FROM Screen", None),
        querysvc.projection("SELECT name FROM Project", None),
        querysvc.projection("SELECT description FROM Screen", None),
        querysvc.projection("SELECT description FROM Project", None),
        querysvc.projection("SELECT details.owner.omeName FROM Screen", None),
        querysvc.projection("SELECT details.owner.omeName FROM Project", None),
        querysvc.projection("SELECT details.group.name FROM Screen", None),
        querysvc.projection("SELECT details.group.name FROM Project", None),
    ]
    if serial:
        for coro in coroutines:
            r = await coro
            print(unwrap(r))
    else:
        rs = await asyncio.gather(*coroutines)
        for r in rs:
            print(unwrap(r))


# https://www.roguelynn.com/words/asyncio-exception-handling/
# https://stackoverflow.com/a/50265468
def handle_exception(loop, context):
    # This is a last resort, should always await exceptions
    # context["exception"] may not exist, context["message"] should
    msg = context.get("exception", context["message"])
    logging.error(f"Unhandled exception: {msg}")

    # first, handle with default handler
    loop.default_exception_handler(context)
    loop.stop()


async def main(serial):
    # Default OMERO client:
    # client = omero.client(HOST)
    # session = client.createSession(USER, PASSWORD)
    # acs = AsyncService(session.getConfigService())
    # aqs = AsyncService(session.getQueryService())

    # Async client:
    client = AsyncClient(HOST)
    session = await client.createSession(USER, PASSWORD)
    try:
        configsvc = await session.getConfigService()
        querysvc = await session.getQueryService()
        await do_stuff(configsvc, querysvc, serial)
    finally:
        client.closeSession()


logging.basicConfig(level=logging.DEBUG)
# True: Run one query at a time, False: run concurrently
serial = False
# serial = True
# asyncio.run(main(serial))

# https://docs.python.org/3.6/library/asyncio-dev.html
loop = asyncio.get_event_loop()
loop.set_debug(True)
loop.set_exception_handler(handle_exception)
start = time.perf_counter()
loop.run_until_complete(main(serial))
end = time.perf_counter() - start
print(f"Time taken for queries: {end:0.2f} seconds.")
