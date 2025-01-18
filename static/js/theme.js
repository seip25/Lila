function theme(){
    const theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    document.body.classList.remove('dark')
    document.body.classList.remove('light')
    document.body.classList.add(`${theme}`)
    return theme
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
   theme()
})