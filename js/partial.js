document.addEventListener("DOMContentLoaded", async () => {
  const aside = document.querySelector("aside");
  const response = await fetch("partials/aside.html");
  const html = await response.text();
  aside.innerHTML = html;
});
