document.addEventListener("DOMContentLoaded", async () => {
  const aside = document.querySelector("aside");
  if (!aside) return;
  try {
    const response = await fetch("partials/aside.html");
    if (!response.ok) throw new Error("Failed to fetch sidebar");
    const html = await response.text();
    aside.innerHTML = html;

    // 1. Dispatch custom event so other scripts (like lila.js) know the aside is fully loaded
    document.dispatchEvent(new CustomEvent("lila:aside-loaded"));

    // 2. Extract and execute script tags within the loaded HTML (since innerHTML doesn't execute them)
    const scripts = aside.querySelectorAll("script");
    scripts.forEach(script => {
      const newScript = document.createElement("script");
      if (script.src) {
        newScript.src = script.src;
      } else {
        newScript.textContent = script.textContent;
      }
      document.body.appendChild(newScript);
      newScript.remove();
    });
  } catch (err) {
    console.error("Error loading aside:", err);
  }
});

