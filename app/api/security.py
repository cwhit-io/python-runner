from app.auth import APITokenAuth


def authenticate_bearer_token(request):
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return APITokenAuth().authenticate(request, parts[1])
