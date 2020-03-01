#!/usr/bin/env python
import asyncio
from functools import partial, update_wrapper
import logging

import Ice
import omero.clients


def _firstline_truncate(s):
    lines = "{}\n".format(s).splitlines()
    if len(lines[0]) > 80 or len(lines) > 1:
        s = lines[0][:79] + "…"
    return s


async def ice_async(loop, func, *args, **kwargs):
    """
    Wrap an asynchronous Ice service method so it can be used with asyncio

    loop: The event loop
    func: The Ice service method
    *args: Positional arguments for the Ice service method
    *kwargs: Keyword arguments for the Ice service method
    """
    # https://docs.python.org/3.6/library/asyncio-task.html#example-future-with-run-until-complete

    # Ice runs in a different thread from asyncio so must use
    # call_soon_threadsafe
    # https://docs.python.org/3.6/library/asyncio-dev.html#concurrency-and-multithreading

    future = loop.create_future()

    def exception_cb(ex):
        logging.warning("exception_cb: %s", _firstline_truncate(ex))
        loop.call_soon_threadsafe(future.set_exception, ex)

    def response_cb(result=None):
        logging.info("response_cb: %s", _firstline_truncate(result))
        loop.call_soon_threadsafe(future.set_result, result)

    a = func(*args, **kwargs, _response=response_cb, _ex=exception_cb)
    logging.debug(
        "_exec_ice_async(%s) sent:%s completed:%s",
        func.__name__,
        a.isSent(),
        a.isCompleted(),
    )

    result = await future
    return result


class AsyncService:
    def __init__(self, svc, loop=None):
        """
        Convert an OMERO Ice service to an async service

        svc: The OMERO Ice service
        loop: The async event loop (optional)
        """

        # This would be easier in Python 3.7 since Future.get_loop() returns
        # the loop the Future is bound to so there's no need to pass it
        # https://docs.python.org/3/library/asyncio-future.html#asyncio.Future.get_loop
        if not loop:
            loop = asyncio.get_event_loop()
        methods = {
            m for m in dir(svc) if callable(getattr(svc, m)) and not m.startswith("_")
        }

        # Ice methods come in sync (`f`) and async (`begin_f`…`end_f`) versions
        # https://doc.zeroc.com/ice/3.6/language-mappings/python-mapping/client-side-slice-to-python-mapping/asynchronous-method-invocation-ami-in-python
        # Replace each set of functions with a single async function `f`.
        # Uses `update_wrapper` to copy the original signature for `f` to the
        # wrapped function.
        async_methods = {m for m in methods if m.startswith("begin_")}
        for async_m in async_methods:
            sync_m = async_m[6:]
            methods.remove(sync_m)
            methods.remove("begin_" + sync_m)
            methods.remove("end_" + sync_m)
            setattr(
                self,
                sync_m,
                update_wrapper(
                    partial(ice_async, loop, getattr(svc, async_m)),
                    getattr(svc, sync_m),
                ),
            )
        for sync_m in methods:
            setattr(
                self,
                sync_m,
                update_wrapper(partial(getattr(svc, sync_m)), getattr(svc, sync_m)),
            )


async def _getServiceWrapper(getsvc_m, loop):
    svc = await getsvc_m()
    return AsyncService(svc, loop)


class AsyncSession(AsyncService):
    def __init__(self, session, loop=None):
        """
        Wrap a session from client.getSession() so all services are async

        session: The OMERO session
        loop: The async event loop (optional)
        """

        # This will wrap methods including getXxxService(), but we need to also
        # wrap the results of those services
        super().__init__(session, loop)
        getsvc_methods = {
            m
            for m in dir(self)
            if callable(getattr(self, m))
            and m.startswith("get")
            and m.endswith("Service")
        }

        for getsvc_m in getsvc_methods:
            setattr(
                self,
                getsvc_m,
                update_wrapper(
                    partial(_getServiceWrapper, getattr(self, getsvc_m), loop),
                    getattr(session, getsvc_m),
                ),
            )


class AsyncClient(omero.clients.BaseClient):
    def __init__(self, args=None, id=None, host=None, port=None, pmap=None):
        super().__init__(args, id, host, port, pmap)

        # Ugly, but there's no other way to override createSession without
        # copying all the code for the class
        self.__agent = self._BaseClient__agent
        self.__cb = self._BaseClient__cb
        self.__ic = self._BaseClient__ic
        self.__ip = self._BaseClient__ip
        self.__lock = self._BaseClient__lock
        self.__logger = self._BaseClient__logger
        self.__oa = self._BaseClient__oa
        self.__previous = self._BaseClient__previous
        self.__sf = self._BaseClient__sf
        self.__uuid = self._BaseClient__uuid

    async def createSession(self, username=None, password=None):
        """
        This is a copy of omero.clients.Baseclient.createSesson
        https://github.com/ome/omero-py/blob/v5.6.1/src/omero/clients.py#L595
        except that:
        - the session is created asynchronously
        - keep alive is not initialised
        """
        self.__lock.acquire()
        try:

            # Checking state

            if self.__sf:
                raise omero.ClientError(
                    "Session already active. "
                    "Create a new omero.client or closeSession()"
                )

            if not self.__ic:
                if not self.__previous:
                    raise omero.ClientError(
                        "No previous data to recreate communicator."
                    )
                self._initData(self.__previous)
                self.__previous = None

            # Check the required properties

            if not username:
                username = self.getProperty("omero.user")
            elif isinstance(username, omero.RString):
                username = username.val

            if not username or len(username) == 0:
                raise omero.ClientError("No username specified")

            if not password:
                password = self.getProperty("omero.pass")
            elif isinstance(password, omero.RString):
                password = password.val

            if not password:
                raise omero.ClientError("No password specified")

            # Acquire router and get the proxy
            prx = None
            retries = 0
            while retries < 3:
                reason = None
                if retries > 0:
                    self.__logger.warning(
                        "%s - createSession retry: %s" % (reason, retries)
                    )
                try:
                    ctx = self.getContext()
                    ctx[omero.constants.AGENT] = self.__agent
                    if self.__ip is not None:
                        ctx[omero.constants.IP] = self.__ip
                    rtr = self.getRouter(self.__ic)
                    prx = await AsyncService(rtr).createSession(
                        username, password, _ctx=ctx
                    )

                    # Create the adapter
                    self.__oa = self.__ic.createObjectAdapterWithRouter(
                        "omero.ClientCallback", rtr
                    )
                    self.__oa.activate()

                    id = Ice.Identity()
                    id.name = self.__uuid
                    id.category = rtr.getCategoryForClient()

                    self.__cb = AsyncClient.CallbackI(self.__ic, self.__oa, id)
                    self.__oa.add(self.__cb, id)

                    break
                except omero.WrappedCreateSessionException as wrapped:
                    if not wrapped.concurrency:
                        raise wrapped  # We only retry concurrency issues.
                    reason = "%s:%s" % (wrapped.type, wrapped.reason)
                    retries = retries + 1
                except Ice.ConnectTimeoutException as cte:
                    reason = "Ice.ConnectTimeoutException:%s" % str(cte)
                    retries = retries + 1

            if not prx:
                raise omero.ClientError("Obtained null object prox")

            # Check type
            sf = omero.api.ServiceFactoryPrx.uncheckedCast(prx)
            if not sf:
                raise omero.ClientError("Obtained object proxy is not a ServiceFactory")
            self.__sf = AsyncSession(sf)

            # Don't automatically configure keep alive

            # Set the client callback on the session
            # and pass it to icestorm
            try:
                raw = self.__oa.createProxy(self.__cb.id)
                await self.__sf.setCallback(
                    omero.api.ClientCallbackPrx.uncheckedCast(raw)
                )
                # self.__sf.subscribe("/public/HeartBeat", raw)
            except BaseException:
                self.__del__()
                raise

            self._BaseClient__cb = self.__cb
            self._BaseClient__oa = self.__oa
            self._BaseClient__sf = self.__sf

            # Set the session uuid in the implicit context
            self.getImplicitContext().put(
                omero.constants.SESSIONUUID, self.getSessionId()
            )

            return self.__sf
        finally:
            self.__lock.release()
