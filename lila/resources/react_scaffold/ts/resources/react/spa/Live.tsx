import { useState } from "react";
import { http } from "@lila";
import { useSSE, useWebSocket } from "@lila/realtime";
import { Badge, Button, Card, Input, toast } from "@/components/ui";

// SSE (Channel) and WebSocketHub demo. Server: app/routes/web/react_pages.py.
export default function Live() {
  const [events, setEvents] = useState<string[]>([]);
  const [messages, setMessages] = useState<string[]>([]);
  const [text, setText] = useState("");
  const sse = useSSE("/app-events", {
    events: { "demo:message": (data) => setEvents((list) => [...list, data.text]) },
  });
  const chat = useWebSocket("/ws/demo", {
    rooms: ["general"],
    events: { "chat:message": (data) => setMessages((list) => [...list, data.text]) },
  });
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <Card title="Server-Sent Events" actions={<Badge tone={sse.connected ? "success" : "warning"} soft>{sse.connected ? "connected" : "connecting"}</Badge>}>
        <Button onClick={() => http("/app-events", { method: "POST", body: { text: `Ping ${new Date().toLocaleTimeString()}` } }).catch((e) => toast.error(e.message))}>
          Publish event
        </Button>
        <ul className="mt-4 space-y-1 text-sm" data-testid="sse-list">{events.map((e, i) => <li key={i}>📨 {e}</li>)}</ul>
      </Card>
      <Card title="WebSocket room" actions={<Badge tone={chat.connected ? "success" : "warning"} soft>{chat.connected ? "connected" : "connecting"}</Badge>}>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (text) chat.emit("chat:message", { text }); setText(""); }}>
          <Input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} wrapperClassName="flex-1" />
          <Button type="submit">Send</Button>
        </form>
        <ul className="mt-4 space-y-1 text-sm" data-testid="ws-list">{messages.map((m, i) => <li key={i}>💬 {m}</li>)}</ul>
      </Card>
    </div>
  );
}
