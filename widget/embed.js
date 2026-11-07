
(function () {
  "use strict";

  const script = document.currentScript;

  if (!script || !script.src) return;

  const widgetUrl = new URL(
    script.dataset.widgetUrl ||
    script.src.replace(/embed\.js(?:\?.*)?$/, "")
  );

  const container = document.createElement("div");
  container.style.width = "100%";

  const iframe = document.createElement("iframe");

  iframe.src = widgetUrl.href;
  iframe.title = "Tobago Moon and Tide Calendar";
  iframe.loading = "lazy";

  iframe.style.width = "100%";
  iframe.style.height = "450px";
  iframe.style.border = "0";
  iframe.style.display = "block";
  iframe.style.overflow = "hidden";

  iframe.setAttribute("scrolling", "no");

  container.appendChild(iframe);

  script.parentNode.insertBefore(container, script);

  window.addEventListener("message", function (event) {

    // Verify the message comes from the widget.
    if (event.origin !== widgetUrl.origin) return;

    if (event.source !== iframe.contentWindow) return;

    const data = event.data;

    if (
      !data ||
      data.type !== "tobago-moon-tide-resize" ||
      !Number.isFinite(data.height)
    ) {
      return;
    }

    const height = Math.max(
      250,
      Math.min(data.height, 3000)
    );

    iframe.style.height = height + "px";

  });

})();
