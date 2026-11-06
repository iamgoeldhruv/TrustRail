
import httpx


class CountingTransport(httpx.AsyncBaseTransport):
    """Counts every request reaching the underlying HTTP transport."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.request_count = 0

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        self.request_count += 1
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()
