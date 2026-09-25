"""
Módulo de compresión y descompresión en streaming para MySqlAutoBkps.
Permite comprimir en gzip al vuelo calculando el hash criptográfico SHA-256
en una sola pasada, sin saturar la memoria RAM ni crear archivos temporales gigantes.
"""

import gzip
import hashlib
import os
import shutil
from typing import BinaryIO, Callable, Optional, Tuple


class StreamCompressor:
    """Motor de compresión en streaming optimizado para archivos SQL."""

    CHUNK_SIZE = 64 * 1024  # 64 KB por fragmento para balance óptimo de I/O

    @classmethod
    def compress_stream(
        cls,
        input_stream: BinaryIO,
        output_file_path: str,
        compression_level: int = 6,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> Tuple[int, str]:
        """
        Lee datos binarios desde un stream (ej. stdout de mysqldump) y escribe
        un archivo comprimido .sql.gz, calculando el hash SHA-256 en vivo.

        Retorna:
            Tuple[tamaño_bytes_comprimido, checksum_sha256]
        """
        sha256 = hashlib.sha256()
        total_compressed_bytes = 0

        # Asegurar directorio destino
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        with open(output_file_path, "wb") as f_out:
            with gzip.GzipFile(filename="", mode="wb", compresslevel=compression_level, fileobj=f_out) as gz_out:
                while True:
                    chunk = input_stream.read(cls.CHUNK_SIZE)
                    if not chunk:
                        break
                    gz_out.write(chunk)
                    sha256.update(chunk)
                    if progress_callback:
                        progress_callback(len(chunk))

        total_compressed_bytes = os.path.getsize(output_file_path)
        return total_compressed_bytes, sha256.hexdigest()

    @classmethod
    def compress_file(
        cls,
        source_file_path: str,
        target_gz_path: str,
        compression_level: int = 6,
        delete_source: bool = False
    ) -> Tuple[int, str]:
        """Comprime un archivo existente a formato .gz."""
        sha256 = hashlib.sha256()
        with open(source_file_path, "rb") as f_in:
            with gzip.open(target_gz_path, "wb", compresslevel=compression_level) as f_out:
                while True:
                    chunk = f_in.read(cls.CHUNK_SIZE)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    sha256.update(chunk)

        if delete_source and os.path.exists(source_file_path):
            os.remove(source_file_path)

        return os.path.getsize(target_gz_path), sha256.hexdigest()

    @classmethod
    def decompress_to_file(cls, gz_file_path: str, target_sql_path: str) -> None:
        """Descomprime un archivo .sql.gz a .sql plano para su restauración o visualización."""
        with gzip.open(gz_file_path, "rb") as f_in:
            with open(target_sql_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out, length=cls.CHUNK_SIZE)

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Formatea un tamaño en bytes a representación legible (ej: 45.2 MB)."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
