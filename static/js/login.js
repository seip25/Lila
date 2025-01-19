async function Login(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
  const resp = await Http({ url: "/login", method: "POST", body: form,token:'token' });
  console.log(resp);

  if(resp.success){
    window.location.replace('/dashboard')
  }
  else{
    Swal.fire({
      title:'Error',
      icon : 'error',
      html : resp.msg || 'Error '
    })
  }
  return ;
}
