import { handleInboundMessage, extractInboundTexts, verifyMetaWebhook, verifySignature } from "./webhook";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname !== "/webhook" && url.pathname !== "/webhook/") {
      return new Response("AI Alpha Squad WhatsApp webhook", { status: 200 });
    }

    if (request.method === "GET") {
      const challenge = verifyMetaWebhook(
        url.searchParams.get("hub.mode"),
        url.searchParams.get("hub.verify_token"),
        url.searchParams.get("hub.challenge"),
        env.WHATSAPP_WEBHOOK_VERIFY_TOKEN,
      );
      if (challenge === null) {
        return new Response("Forbidden", { status: 403 });
      }
      return new Response(challenge, { status: 200 });
    }

    if (request.method === "POST") {
      const rawBody = await request.text();
      const ok = await verifySignature(request, env.WHATSAPP_APP_SECRET, rawBody);
      if (!ok) {
        return new Response("Invalid signature", { status: 401 });
      }

      let payload: unknown;
      try {
        payload = JSON.parse(rawBody);
      } catch {
        return new Response("Bad JSON", { status: 400 });
      }

      const messages = extractInboundTexts(payload);
      for (const msg of messages) {
        await handleInboundMessage(env, msg.from, msg.text!.body!);
      }

      return new Response("OK", { status: 200 });
    }

    return new Response("Method not allowed", { status: 405 });
  },
};
