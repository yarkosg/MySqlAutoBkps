"""
Excepciones personalizadas para MySqlAutoBkps.
Permite un manejo estructurado, legible y seguro de errores en todas las capas del sistema.
"""

class MySqlAutoBkpsError(Exception):
    """Excepción base para todos los errores de la aplicación."""
    def __init__(self, message: str, details: str = ""):
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Detalle: {self.details}"
        return self.message


class SecurityError(MySqlAutoBkpsError):
    """Excepción lanzada cuando ocurre un error en el cifrado o descifrado de credenciales."""
    pass


class ConfigurationError(MySqlAutoBkpsError):
    """Excepción lanzada por errores de lectura, escritura o validación de configuración."""
    pass


class DatabaseConnectionError(MySqlAutoBkpsError):
    """Excepción lanzada cuando no se puede establecer conexión con un servidor MySQL/MariaDB."""
    pass


class DumpEngineNotFoundError(MySqlAutoBkpsError):
    """Excepción lanzada cuando no se encuentra mysqldump / mariadb-dump en el sistema."""
    pass


class BackupExecutionError(MySqlAutoBkpsError):
    """Excepción lanzada cuando un proceso de respaldo (Full o Incremental) falla."""
    pass


class RetentionError(MySqlAutoBkpsError):
    """Excepción lanzada durante la purga de respaldos antiguos."""
    pass


class SchedulerError(MySqlAutoBkpsError):
    """Excepción lanzada por fallos en el programador de tareas automáticas."""
    pass
