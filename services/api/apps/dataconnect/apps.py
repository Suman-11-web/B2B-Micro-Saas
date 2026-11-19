from django.apps import AppConfig


class DataConnectConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dataconnect'
    verbose_name = 'Data Connectors (Database Integration)'