# OMERO Python asyncio

Example of using asyncio with OMERO Ice methods.

Compare the time taken to run multiple HQL queries serially (`serial=True`, around 3 seconds) and concurrently (`serial=False`, around 1 second).

In Ice 3.6 all synchonous methods also have asynchronous versions prefixed with `begin_` and `end_`: https://doc.zeroc.com/ice/3.6/language-mappings/python-mapping/client-side-slice-to-python-mapping/asynchronous-method-invocation-ami-in-python
If callbacks are used it is possible to avoid explicitly calling `end_` when the asynchronous call finished.

With a bit of additional wrapping it is possible to integrate these Ice asynchronous calls into Python's `asyncio` framework.

Note in Ice 3.7 this would be a lot easier as Ice provides a wrapper to return `asyncio.Future`s directly: https://doc.zeroc.com/ice/3.7/language-mappings/python-mapping/client-side-slice-to-python-mapping/asynchronous-method-invocation-ami-in-python/ami-in-python-with-futures#id-.AMIinPythonwithFuturesv3.7-asyncioIntegration
