async function Register(event) {
  event.preventDefault();
  const form = Object.fromEntries(new FormData(event.target));
 
  const resp = await Http({ url: "/register", method: "POST", body: form, loading:true });
  if(resp.success==false){
    Swal.fire({
      icon:'error',
      html :resp.msg || 'Error',
      title:'Error'
    })
    return false;
  }
  else{
    Swal.fire({
      icon:'success',
      html :resp.msg || '',
      title:'Ok'
    })

    window.location.replace('/dashboard')
  }
}
