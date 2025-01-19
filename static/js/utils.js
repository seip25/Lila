async function Http({
  url = "/",
  method = "GET",
  body = false,
  token = false,
}) {
  const options = {
    method: method,
    headers: {},
  };
  if (body) options["body"] = JSON.stringify(body);

  if (token) options.headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || "Error fetch");
  }
  const resp = await response.json();
  return resp;
}

function setCookie({ name = "token", value, days = 7, secure = false }) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  let cookieString = `${name}=${encodeURIComponent(
    value
  )}; expires=${expires}; path=/; SameSite=Lax`;
  if (secure) cookieString += "; Secure";

  document.cookie = cookieString;
}

function getCookie({ name }) {
  return document.cookie.split("; ").reduce((r, v) => {
    const parts = v.split("=");
    return parts[0] === name ? decodeURIComponent(parts[1]) : r;
  }, "");
}

function deleteCookie({ name }) {
  document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
}

function openMenu({ event = false, id = "drawer" }) {
  if (event) event.preventDefault();
  const element = document.querySelector(`#${id}`);
  element.classList.add("active");
}

function closeMenu({ event = false, id = "drawer" }) {
  if (event) event.preventDefault();
  const element = document.querySelector(`#${id}`);
  element.classList.remove("active");
}
