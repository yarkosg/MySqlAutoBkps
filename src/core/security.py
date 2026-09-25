"""
Módulo de seguridad y criptografía para MySqlAutoBkps.
Utiliza Fernet (cifrado simétrico autenticado AES-128-CBC + HMAC-SHA256)
para garantizar que ninguna contraseña de base de datos se guarde en texto plano.
Si la clave local no existe, se genera automáticamente de forma silenciosa.
"""

import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from src.core.exceptions import SecurityError


class SecretManager:
    """Gestiona el ciclo de vida de la clave criptográfica local y el cifrado de datos."""

    def __init__(self, key_path: Optional[str] = None):
        if key_path is None:
            config_dir = os.path.join(os.getcwd(), "config")
            os.makedirs(config_dir, exist_ok=True)
            self.key_path = os.path.join(config_dir, ".key")
        else:
            self.key_path = key_path

        self._fernet: Optional[Fernet] = None
        self._ensure_key_exists()

    def _ensure_key_exists(self) -> None:
        """
        Verifica si la clave maestra existe; si no, la genera y guarda
        silenciosamente sin interrumpir al usuario.
        """
        try:
            os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
            if not os.path.exists(self.key_path):
                # Generar una clave segura aleatoria de 32 bytes en formato URL-safe base64
                key = Fernet.generate_key()
                with open(self.key_path, "wb") as key_file:
                    key_file.write(key)

                # Intentar proteger permisos en sistemas Unix
                try:
                    os.chmod(self.key_path, 0o600)
                except Exception:
                    pass

            with open(self.key_path, "rb") as key_file:
                key = key_file.read().strip()
                self._fernet = Fernet(key)

        except Exception as e:
            raise SecurityError(
                "Error crítico al inicializar el gestor de claves de seguridad",
                details=str(e)
            )

    def encrypt_text(self, plaintext: str) -> str:
        """
        Cifra una cadena de texto en formato seguro base64.
        Si la cadena está vacía (por ejemplo, contraseñas vacías en XAMPP local), la preserva.
        """
        if not plaintext:
            return ""
        if not self._fernet:
            self._ensure_key_exists()

        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as e:
            raise SecurityError("Fallo al cifrar credencial sensible", details=str(e))

    def decrypt_text(self, ciphertext: str) -> str:
        """
        Descifra una cadena previamente cifrada con Fernet.
        """
        if not ciphertext:
            return ""
        if not self._fernet:
            self._ensure_key_exists()

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            raise SecurityError("Token de cifrado inválido o clave corrupta/cambiada.")
        except Exception as e:
            raise SecurityError("Fallo al descifrar credencial sensible", details=str(e))

    @staticmethod
    def mask_text(text: str) -> str:
        """Retorna una versión ofuscada para interfaces visuales o logs (ej: '******')."""
        if not text:
            return "(vacía)"
        return "•" * min(len(text), 10)


# Instancia singleton predeterminada
secret_manager = SecretManager()
