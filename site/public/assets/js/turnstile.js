(async function () {
  const container = document.getElementById("turnstile-widget");
  const tokenInput = document.getElementById("ts-token");
  if (!container || !tokenInput) return;

  let siteKey;
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    siteKey = cfg.turnstileSiteKey;
  } catch {
    siteKey = "1x00000000000000000000AA";
  }

  function render() {
    if (!window.turnstile) return;
    window.turnstile.render(container, {
      sitekey: siteKey,
      theme: "dark",
      callback: (token) => { tokenInput.value = token; },
      "expired-callback": () => { tokenInput.value = ""; },
    });
  }

  if (window.turnstile) {
    render();
  } else {
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    s.async = true;
    s.onload = render;
    document.head.appendChild(s);
  }
})();
