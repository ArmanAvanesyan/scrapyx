class DebugRequestMiddleware:
    """Logs outgoing requests (method, URL, headers, meta) at debug level."""
    def process_request(self, request, spider):
        spider.logger.debug(f"[Debug] {request.method} {request.url}")
        spider.logger.debug(f"[Debug] Headers={dict(request.headers)} Meta={request.meta}")
