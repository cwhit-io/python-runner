from ninja.security import HttpBearer
from .models import APIToken


class APITokenAuth(HttpBearer):
    """
    API Token authentication for Django Ninja.
    
    Usage in API routes:
        @api.get("/protected", auth=APITokenAuth())
        def protected_endpoint(request):
            # request.auth contains the APIToken object
            return {"user": request.auth.user.username}
    """
    
    def authenticate(self, request, token):
        try:
            api_token = APIToken.objects.select_related('user').get(
                token=token,
                is_active=True
            )
            return api_token
        except APIToken.DoesNotExist:
            return None
