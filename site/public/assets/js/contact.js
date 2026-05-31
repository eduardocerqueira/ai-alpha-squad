(function () {
  const form = document.getElementById("contact-form");
  if (!form) return;

  const status = document.getElementById("form-status");
  const submitBtn = form.querySelector('button[type="submit"]');

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    status.textContent = "";
    status.className = "form-status";

    const token = form.querySelector("#ts-token")?.value;

    if (!token) {
      status.textContent = "Please complete the verification.";
      status.className = "form-status err";
      return;
    }

    const data = {
      name: document.getElementById("name").value,
      email: document.getElementById("email").value,
      message: document.getElementById("message").value,
      turnstileToken: token,
    };

    submitBtn.disabled = true;
    submitBtn.textContent = "Sending…";

    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.error || "Send failed");
      }

      status.textContent = json.message || "Message sent.";
      status.className = "form-status ok";
      form.reset();
      if (window.turnstile) window.turnstile.reset();
    } catch (err) {
      status.textContent = err.message || "Something went wrong. Try contact@aialphasquad.com directly.";
      status.className = "form-status err";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Send message";
    }
  });
})();
