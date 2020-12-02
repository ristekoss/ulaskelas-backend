from django.http import HttpResponseRedirect
from .utils import (
    get_cas_client,
    get_service_url,
    authenticate,
)


def with_sso_ui(force_login=True):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            service_url = get_service_url(request)
            client = get_cas_client(service_url)
            login_url = client.get_login_url()

            ticket = request.GET.get("ticket")
            if ticket:
                sso_profile = authenticate(ticket, client)

                if sso_profile is None and force_login:
                    return HttpResponseRedirect(login_url)

                kwargs.update({"sso_profile": sso_profile})
                return func(request, *args, **kwargs)
            else:
                return HttpResponseRedirect(login_url)

        return wrapper

    return decorator
