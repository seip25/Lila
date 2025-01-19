async function Login(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const resp = await Http({
    url: "/login",
    method: "POST",
    body: form,
    token: "token",
    loading:true
  });
  console.log(resp);

  if (resp.success) {
    cookie = await setCookie({ name: "token", value: resp.token });
    window.location.replace("/dashboard");
  } else {
    Swal.fire({
      title: "Error",
      icon: "error",
      html: resp.msg || "Error ",
    });
  }
  return;
}
