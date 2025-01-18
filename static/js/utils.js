
async function Http( url = '/', method = 'GET', body = false) {
    const options = {
        method: method,
    };
    if (body) options["body"] = JSON.stringify(body)
    const json = await fetch(url, options)
    const resp = await json.json()
    return resp
}