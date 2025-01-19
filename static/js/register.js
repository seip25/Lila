async function Register(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const resp = await Http({ url: "/register", method: "POST", body: form });
  console.log(resp);

  alert(JSON.stringify(resp));
}
