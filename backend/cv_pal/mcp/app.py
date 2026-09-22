"""The MCP server as an ASGI app, mounted into the API at ``/mcp``."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from cv_pal.mcp.runtime import hooks
from cv_pal.mcp.server import mcp

MOUNT_PATH = "/mcp"

# Stateless and JSON: every tool is a single request and answer, so there is no stream
# to keep open through nginx and no session to lose when the backend restarts.
mcp_app = mcp.http_app(path="/", stateless_http=True, json_response=True)


class EnabledGate:
    """Answer 404 unless the operator turned the endpoint on.

    Checked per request rather than at import, so the setting is read the same way the
    rest of the app reads configuration.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the MCP app.

        Args:
            app: The app to guard.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass the request through, or refuse it when the endpoint is off.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] == "http" and not hooks.settings().mcp_enabled:
            response = JSONResponse({"detail": "Not Found"}, status_code=404)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class ExactMountPath:
    """Serve ``/mcp`` as ``/mcp/`` instead of redirecting.

    Starlette answers a mount's bare path with a redirect to the slashed one, built from
    the Host header. Behind nginx that URL lacks the ``/api`` prefix, so an agent
    configured without the trailing slash would be sent somewhere that does not exist.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Wrap the application.

        Args:
            app: The app to wrap.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Rewrite the bare mount path, and pass everything through.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        if scope["type"] == "http" and scope["path"] == MOUNT_PATH:
            scope = {
                **scope,
                "path": f"{MOUNT_PATH}/",
                "raw_path": f"{MOUNT_PATH}/".encode(),
            }
        await self.app(scope, receive, send)
