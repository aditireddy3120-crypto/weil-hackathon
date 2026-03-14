from datetime import datetime
from typing import Any, Dict
import os

try:
    from weilliptic_sdk.audit import AuditClient  # type: ignore
except ImportError:
    class AuditClient:  # type: ignore
        def __init__(self, applet_id: str) -> None:
            self.applet_id = applet_id

        async def append_record(
            self, namespace: str, flow_id: str, record: Dict[str, Any]
        ) -> None:
            print(f'[AUDIT:{namespace}:{flow_id}] {record}')


class WeilAuditLogger:
    '''Wrapper over the Weilchain audit service that enriches every agent step.'''

    def __init__(self, applet_id: str, namespace: str) -> None:
        self.client = AuditClient(applet_id=applet_id)
        self.namespace = namespace

    def dashboard_url(self, flow_id: str) -> str:
        base = os.getenv("WEIL_AUDIT_BASE", "https://audit.weilliptic.ai")
        return f"{base}/{self.namespace}/{flow_id}"

    async def log_event(
        self, flow_id: str, event_type: str, payload: Dict[str, Any]
    ) -> None:
        record: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'event_type': event_type,
            'payload': payload,
        }
        await self.client.append_record(
            namespace=self.namespace, flow_id=flow_id, record=record
        )

    async def log_tool_event(
        self, flow_id: str, step: str, tool: str, detail: Dict[str, Any]
    ) -> None:
        payload = {'step': step, 'tool': tool, 'detail': detail}
        await self.log_event(flow_id=flow_id, event_type='tool_event', payload=payload)
