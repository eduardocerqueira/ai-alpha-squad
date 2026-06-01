/**
 * DashboardHub — a single Durable Object that holds the open Director dashboards'
 * WebSocket connections and broadcasts a "refresh" the moment CI publishes new
 * data (the workflow POSTs /api/director/notify on completion). Uses the
 * hibernation API so idle sockets cost nothing.
 */
export class DashboardHub implements DurableObject {
  private ctx: DurableObjectState;

  constructor(ctx: DurableObjectState) {
    this.ctx = ctx;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    // CI → broadcast a refresh to every connected dashboard.
    if (url.pathname.endsWith("/notify")) {
      const sockets = this.ctx.getWebSockets();
      const msg = JSON.stringify({ type: "refresh" });
      for (const ws of sockets) {
        try {
          ws.send(msg);
        } catch {
          /* dropped socket; ignore */
        }
      }
      return new Response(JSON.stringify({ ok: true, clients: sockets.length }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Dashboard → open a WebSocket and wait for refresh pings.
    if (request.headers.get("Upgrade")?.toLowerCase() === "websocket") {
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);
      this.ctx.acceptWebSocket(server);
      return new Response(null, { status: 101, webSocket: client });
    }

    return new Response("expected websocket", { status: 426 });
  }

  // Heartbeat so the client can keep the connection alive through proxies.
  webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): void {
    if (message === "ping") {
      try {
        ws.send("pong");
      } catch {
        /* ignore */
      }
    }
  }

  webSocketClose(ws: WebSocket, code: number): void {
    try {
      ws.close(code);
    } catch {
      /* ignore */
    }
  }
}
