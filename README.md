# OMERO Python asyncio
[![Build Status](https://travis-ci.com/manics/omero-asyncio.svg?branch=master)](
https://travis-ci.com/manics/omero-asyncio)

OMERO.py client and services that works with [`asyncio`](https://docs.python.org/3.6/library/asyncio.html).

For example, compare the time taken to run multiple HQL queries in [`example.py`](example/example.py)  serially (`serial=True`, around 3 seconds) and concurrently (`serial=False`, around 1 second).


# Async Classes

## `AsyncService`

Use this if you are using the standard (synchronous) `omero.client` and want easy access to async services.
For example:
```python
client = omero.client(HOST)
session = client.createSession(USERNAME, PASSWORD)

qs = AsyncService(session.getQueryService())
result = await qs.findAllByQuery('From Project', None)
```

Note due to differences in the positions of the underlying async keyword parameters if you need to pass an Ice context parameter this must be a named argument `_ctx=ctx`.


## `AsyncClient`

This is a modified version of the [default `omero.client`](https://github.com/ome/omero-py/blob/v5.6.1/src/omero/clients.py#L48) with an async implementation of [`createSession`](https://github.com/ome/omero-py/blob/v5.6.1/src/omero/clients.py#L595).
Services are automatically converted to async.
For example:
```python
client = AsyncClient(HOST)
session = await client.createSession(USERNAME, PASSWORD)

qs = await session.getQueryService()
result = await qs.findAllByQuery('From Project', None)
```


# Implementation

In Ice 3.6 all synchonous methods [also have asynchronous versions prefixed with `begin_` and `end_`](https://doc.zeroc.com/ice/3.6/language-mappings/python-mapping/client-side-slice-to-python-mapping/asynchronous-method-invocation-ami-in-python).
If callbacks are used it is possible to avoid explicitly calling `end_` when the asynchronous call finishes.

With a bit of additional wrapping it is possible to integrate these Ice asynchronous calls into Python's `asyncio` framework.
A wrapper class `AsyncService` is used to wrap Ice services to automatically convert all methods to their async form.

Note in Ice 3.7 this would be a lot easier as [Ice provides a wrapper to return `asyncio.Future`s directly](https://doc.zeroc.com/ice/3.7/language-mappings/python-mapping/client-side-slice-to-python-mapping/asynchronous-method-invocation-ami-in-python/ami-in-python-with-futures#id-.AMIinPythonwithFuturesv3.7-asyncioIntegration).

Also note that although this enables concurrent Ice calls it is still [restricted to a single thread](https://doc.zeroc.com/frequently-asked-questions/ice-for-python-faqs/how-does-multi-threading-work-with-ice-for-python).
