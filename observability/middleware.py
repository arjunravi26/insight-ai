import time

from observability.metrics import (
    HTTP_REQUESTS,
    HTTP_REQUEST_LATENCY,
    HTTP_REQUESTS_IN_PROGRESS,
)


class PrometheusMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Don't measure Prometheus scraping itself.
        if scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")

        status_code = 500
        start_time = time.perf_counter()

        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=method
        ).inc()

        async def send_wrapper(message):

            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_wrapper
            )

        finally:
            duration = time.perf_counter() - start_time

            route_object = scope.get("route")

            # Use the route template, not a raw URL containing IDs.
            route = getattr(
                route_object,
                "path",
                "unmatched"
            )

            HTTP_REQUESTS.labels(
                method=method,
                route=route,
                status_code=str(status_code)
            ).inc()

            HTTP_REQUEST_LATENCY.labels(
                method=method,
                route=route
            ).observe(duration)

            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=method
            ).dec()