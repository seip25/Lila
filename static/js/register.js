async function Register(event) {
    event.preventDefault();
    const form = Object.fromEntries(new FormData(event.target))
    const resp=await Http('/input', 'POST', form)
    console.log(resp)

    alert(JSON.stringify(resp))
}