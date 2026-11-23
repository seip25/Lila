document.addEventListener("DOMContentLoaded", async () => {
  const aside = document.querySelector("aside");
  if (!aside) return;
  try {
    const response = await fetch("partials/aside.html");
    if (!response.ok) throw new Error("Failed to fetch sidebar");
    const html = await response.text();
    aside.innerHTML = html;

    // 1. Execute script tags within the loaded HTML synchronously so active links are marked before cloning into drawer
    const scripts = aside.querySelectorAll("script");
    scripts.forEach((script) => {
      const newScript = document.createElement("script");
      if (script.src) {
        newScript.src = script.src;
      } else {
        newScript.textContent = script.textContent;
      }
      document.body.appendChild(newScript);
      newScript.remove();
    });

    // 2. Notify listeners (e.g., lila.js mobile drawer) after active link highlighting has run
    document.dispatchEvent(new CustomEvent("lila:aside-loaded"));
  } catch (err) {
    console.error("Error loading aside:", err);
  }
});
