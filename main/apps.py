from django.apps import AppConfig

class MainConfig(AppConfig):
    name = 'main'

    def ready(self):
        # Makes sure all signal handlers are connected
        from main import handlers  # noqa
