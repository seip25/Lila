//English : Example utils.js for fetch and cookies (get,post,put,etc and  jwt token)
//Español: Ejemplo de utils.js para fetch y cookies (get,post,put,etc y token jwt).

// Ejemplo de búsqueda, para obtener el ID de usuario y el token , en el cliente(token de sesión, no jwt)
//  const token=await getCookie({name:'token'})
//  const resp=await fetch('/api/token',{ headers:{
//  'Authorization': 'Bearer '+token
//  }
//  })

// Example of fetch, to get the user ID and token, on the client (session token, not jwt)
// const token=await getCookie({name:'token'})
// const resp=await fetch('/api/token',{ headers:{
// 'Authorization': 'Bearer '+token
// }
// })
async function Http({
  url = "/",
  method = "GET",
  body = false,
  token_jwt = false
}) {
 
  const options = {
    method: method,
    headers: {},
  };
  if (body) options["body"] = JSON.stringify(body);

  //JWT Token
  if (token_jwt) {
    const token = await getCookie({ name: "token" });
    options.headers["Authorization"] = `Bearer ${token}`; 
  }
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
