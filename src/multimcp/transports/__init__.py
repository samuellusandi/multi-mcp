"""Transport implementations for MultiMCP."""

from ..constants import TRANSPORT_SSE, TRANSPORT_STDIO, TRANSPORT_STREAM
from .sse_transport import SSETransport
from .stdio_transport import StdioTransport
from .stream_transport import StreamTransport

TRANSPORT_CLASSES = {
    TRANSPORT_STDIO: StdioTransport,
    TRANSPORT_SSE: SSETransport,
    TRANSPORT_STREAM: StreamTransport,
}
