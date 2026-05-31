export async function sendTextMessage(env: Env, body: string): Promise<void> {
  if (!env.WHATSAPP_ACCESS_TOKEN || !env.WHATSAPP_PHONE_NUMBER_ID) {
    console.warn("WhatsApp send skipped — missing ACCESS_TOKEN or PHONE_NUMBER_ID");
    return;
  }
  const to = env.WHATSAPP_DIRECTOR_PHONE.replace(/\D/g, "");
  const res = await fetch(
    `https://graph.facebook.com/v21.0/${env.WHATSAPP_PHONE_NUMBER_ID}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.WHATSAPP_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to,
        type: "text",
        text: { body },
      }),
    },
  );
  if (!res.ok) {
    const text = await res.text();
    console.error("WhatsApp send failed", res.status, text);
  }
}
