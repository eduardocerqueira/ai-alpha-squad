(function () {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const canvas = document.getElementById("grid");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  let w, h, cols, rows, spacing, offset = 0;

  function resize() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    spacing = Math.max(40, Math.min(80, w / 24));
    cols = Math.ceil(w / spacing) + 1;
    rows = Math.ceil(h / spacing) + 1;
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    offset += 0.3;

    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        const px = x * spacing;
        const py = y * spacing + Math.sin((x + offset) * 0.15) * 8;
        const dist = Math.hypot(px - w / 2, py - h / 2);
        const alpha = Math.max(0, 0.35 - dist / (Math.max(w, h) * 0.9));
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fillRect(px, py, 1, 1);
      }
    }

    ctx.strokeStyle = "rgba(255,255,255,0.04)";
    ctx.lineWidth = 1;
    for (let x = 0; x < cols; x++) {
      const px = x * spacing;
      ctx.beginPath();
      ctx.moveTo(px, 0);
      ctx.lineTo(px, h);
      ctx.stroke();
    }
    for (let y = 0; y < rows; y++) {
      const py = y * spacing;
      ctx.beginPath();
      ctx.moveTo(0, py);
      ctx.lineTo(w, py);
      ctx.stroke();
    }

    requestAnimationFrame(draw);
  }

  resize();
  draw();
  window.addEventListener("resize", resize);
})();
