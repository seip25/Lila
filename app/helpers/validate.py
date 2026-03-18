from core.responses import JSONResponse


def responseValidationError(e):
    errors = []
    msg_errors = ""
    for err in e.errors():
        field = err["loc"][0]
        msg = err["msg"]
        errors.append({field: msg})
        msg_errors += f"""{err['loc'][0]} : {msg} .  """

    return JSONResponse(
        {"success": False, "errors": errors, "msg": msg_errors},
        status_code=400,
    )