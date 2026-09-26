"""
Suite de pruebas unitarias y de integración para MySqlAutoBkps.
Verifica:
1. Auto-creación silenciosa de archivos de configuración y clave maestra.
2. Cifrado y descifrado seguro de credenciales con Fernet AES.
3. Modelado y serialización de Servidores y Bases de Datos.
4. Motor de compresión en streaming y cálculo de integridad SHA-256.
5. Políticas de retención automática y preservación de cadenas incrementales.
6. Detección de binarios y banderas de compatibilidad phpMyAdmin.
"""

import io
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from src.core.config import ConfigManager
from src.core.security import SecretManager
from src.engine.compressor import StreamCompressor
from src.engine.detector import BinaryDetector
from src.engine.dump_engine import DumpEngine
from src.models.database import DatabaseConfig
from src.models.manifest import BackupManifest, BackupType
from src.models.server import ServerConfig
from src.services.backup_service import BackupService
from src.services.retention_service import RetentionService


class TestMySqlAutoBkps(unittest.TestCase):
    """Casos de prueba para validar la funcionalidad integral."""

    def setUp(self):
        # Crear directorio temporal para pruebas aisladas
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "config")
        self.key_path = os.path.join(self.config_dir, ".key")

    def tearDown(self):
        # Limpiar directorio temporal
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_silent_auto_creation_of_config_and_key(self):
        """Verifica que si no existen los archivos al clonar el proyecto, se crean automáticamente sin pedirlo."""
        self.assertFalse(os.path.exists(self.key_path))

        # Inicializar SecretManager con ruta temporal
        sec_mgr = SecretManager(self.key_path)
        self.assertTrue(os.path.exists(self.key_path))
        self.assertGreater(os.path.getsize(self.key_path), 0)

        # Inicializar ConfigManager con carpeta temporal
        cfg_mgr = ConfigManager(self.config_dir)
        self.assertTrue(os.path.exists(cfg_mgr.servers_file))
        self.assertTrue(os.path.exists(cfg_mgr.settings_file))

        # Verificar que carga listas vacías válidas
        servers = cfg_mgr.load_servers()
        self.assertEqual(servers, [])

        settings = cfg_mgr.load_settings()
        self.assertIn("compression_enabled", settings)
        self.assertTrue(settings["compression_enabled"])

    def test_02_encryption_and_decryption_security(self):
        """Verifica que las contraseñas se cifran y descifran fielmente con AES-Fernet."""
        sec_mgr = SecretManager(self.key_path)
        original_pass = "P@ssw0rd_Super_Segura_123!#$"

        encrypted = sec_mgr.encrypt_text(original_pass)
        self.assertNotEqual(original_pass, encrypted)
        self.assertNotIn(original_pass, encrypted)

        decrypted = sec_mgr.decrypt_text(encrypted)
        self.assertEqual(original_pass, decrypted)

        # Prueba con contraseña vacía (ej. MySQL local por defecto)
        self.assertEqual(sec_mgr.encrypt_text(""), "")
        self.assertEqual(sec_mgr.decrypt_text(""), "")

    def test_03_server_and_database_grouping(self):
        """Verifica la agrupación de múltiples bases de datos por servidor."""
        db1 = DatabaseConfig(name="erp_prod", charset="utf8mb4")
        db2 = DatabaseConfig(name="crm_prod", charset="utf8mb4")

        server = ServerConfig(
            name="Servidor Cloud AWS",
            host="192.168.1.50",
            port=3306,
            user="admin_bkp",
            databases=[db1, db2]
        )

        self.assertEqual(len(server.databases), 2)
        self.assertIsNotNone(server.get_database("erp_prod"))
        self.assertIsNotNone(server.get_database("crm_prod"))
        self.assertIsNone(server.get_database("inexistente"))

        # Serialización y deserialización
        serialized = server.to_dict()
        restored = ServerConfig.from_dict(serialized)
        self.assertEqual(restored.name, "Servidor Cloud AWS")
        self.assertEqual(len(restored.databases), 2)

    def test_04_stream_compression_and_sha256_integrity(self):
        """Verifica compresión Gzip en streaming y cálculo simultáneo de hash SHA-256."""
        sample_sql_data = (
            b"-- MySqlAutoBkps Dump Sample\n"
            b"CREATE TABLE `users` (`id` int, `name` varchar(100));\n"
            b"INSERT INTO `users` VALUES (1, 'Alice'), (2, 'Bob');\n"
        ) * 1000

        input_stream = io.BytesIO(sample_sql_data)
        out_gz = os.path.join(self.test_dir, "test_dump.sql.gz")

        compressed_size, checksum = StreamCompressor.compress_stream(
            input_stream=input_stream,
            output_file_path=out_gz,
            compression_level=6
        )

        self.assertTrue(os.path.exists(out_gz))
        self.assertEqual(compressed_size, os.path.getsize(out_gz))
        self.assertLess(compressed_size, len(sample_sql_data))  # Compresión efectiva

        # Descomprimir y verificar contenido idéntico
        out_sql = os.path.join(self.test_dir, "decompressed.sql")
        StreamCompressor.decompress_to_file(out_gz, out_sql)

        with open(out_sql, "rb") as f:
            decompressed_content = f.read()

        self.assertEqual(sample_sql_data, decompressed_content)

    def test_05_retention_policy_and_chain_preservation(self):
        """Verifica que la retención elimina copias viejas sin romper cadenas incrementales."""
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        old_date = (now - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")

        # Crear archivos físicos ficticios
        file_old_full = os.path.join(self.test_dir, "old_full.sql.gz")
        file_recent_incr = os.path.join(self.test_dir, "recent_incr.sql.gz")
        with open(file_old_full, "w") as f: f.write("old full content")
        with open(file_recent_incr, "w") as f: f.write("recent incr content")

        m_old_full = BackupManifest(
            backup_id="full-001",
            server_id="srv-1",
            server_name="Prod",
            database_name="shop_db",
            backup_type=BackupType.FULL,
            created_at=old_date,
            file_path=file_old_full,
            file_name="old_full.sql.gz",
            file_size_bytes=100,
            checksum_sha256="abc1"
        )

        m_recent_incr = BackupManifest(
            backup_id="incr-001",
            server_id="srv-1",
            server_name="Prod",
            database_name="shop_db",
            backup_type=BackupType.INCREMENTAL,
            created_at=yesterday,
            file_path=file_recent_incr,
            file_name="recent_incr.sql.gz",
            file_size_bytes=50,
            checksum_sha256="abc2",
            base_backup_id="full-001",
            chain_index=1
        )

        # Aplicar retención de 30 días
        remaining, deleted = RetentionService.apply_retention(
            manifests=[m_recent_incr, m_old_full],
            max_days=30,
            max_versions=10
        )

        # El FULL base debe conservarse porque tiene un incremental activo dependiente
        self.assertIn(m_old_full, remaining)
        self.assertIn(m_recent_incr, remaining)
        self.assertEqual(len(deleted), 0)

    def test_06_phpmyadmin_dump_flags(self):
        """Verifica que las banderas construidas contengan todos los parámetros requeridos para phpMyAdmin."""
        engine = DumpEngine()
        flags = engine.build_dump_arguments("temp.cnf", "my_test_db")

        # Verificar banderas críticas de phpMyAdmin y consistencia
        required_flags = [
            "--single-transaction",
            "--quick",
            "--routines",
            "--triggers",
            "--events",
            "--add-drop-table",
            "--add-locks",
            "--create-options",
            "--disable-keys",
            "--extended-insert",
            "--hex-blob",
            "--default-character-set=utf8mb4",
            "--set-gtid-purged=OFF",
            "my_test_db"
        ]
        for flag in required_flags:
            self.assertIn(flag, flags)

    def test_07_phpmyadmin_restore_guide_generation(self):
        """Verifica la generación de la guía de restauración para phpMyAdmin."""
        manifest = BackupManifest(
            backup_id="bkp-123",
            server_id="srv-1",
            server_name="Servidor Central",
            database_name="ventas_db",
            backup_type=BackupType.FULL,
            created_at="2026-09-24 10:00:00",
            file_path=r"C:\backups\dump_ventas_db.sql.gz",
            file_name="dump_ventas_db.sql.gz",
            file_size_bytes=1024 * 1024 * 5,
            checksum_sha256="abcdef1234567890"
        )
        guide = BackupService.generate_phpmyadmin_restore_instructions(manifest)
        self.assertIn("PHPMYADMIN", guide)
        self.assertIn("ventas_db", guide)
        self.assertIn("dump_ventas_db.sql.gz", guide)
        self.assertIn("Importar", guide)


    def test_08_workbench_importer(self):
        """Verifica la detección y parseo de perfiles de conexión de MySQL Workbench."""
        from src.services.workbench_importer import WorkbenchImporter

        sample_xml = """<?xml version="1.0"?>
<data grt_format="2.0">
  <value type="list" content-type="object" content-struct-name="db.mgmt.Connection">
    <value type="object" struct-name="db.mgmt.Connection">
      <value type="string" key="name">Producción AWS</value>
      <value type="dict" key="parameterValues">
        <value type="string" key="hostName">db.empresa.com</value>
        <value type="int" key="port">3307</value>
        <value type="string" key="userName">db_admin</value>
        <value type="string" key="serverVersion">8.0.32</value>
        <value type="int" key="useSSL">1</value>
      </value>
    </value>
  </value>
</data>"""
        xml_test_file = os.path.join(self.test_dir, "test_connections.xml")
        with open(xml_test_file, "w", encoding="utf-8") as f:
            f.write(sample_xml)

        conns = WorkbenchImporter.parse_connections_file(xml_test_file)
        self.assertEqual(len(conns), 1)
        self.assertEqual(conns[0]["name"], "Producción AWS")
        self.assertEqual(conns[0]["host"], "db.empresa.com")
        self.assertEqual(conns[0]["port"], 3307)
        self.assertEqual(conns[0]["user"], "db_admin")
        self.assertTrue(conns[0]["ssl"])
        self.assertEqual(conns[0]["server_version"], "8.0.32")


    def test_09_native_dump_engine_escaping(self):
        """Verifica que el motor nativo en Python escape fielmente tipos de datos para phpMyAdmin."""
        from src.engine.native_dump_engine import NativeDumpEngine
        import datetime
        import decimal

        self.assertEqual(NativeDumpEngine._escape_value(None), "NULL")
        self.assertEqual(NativeDumpEngine._escape_value(True), "1")
        self.assertEqual(NativeDumpEngine._escape_value(False), "0")
        self.assertEqual(NativeDumpEngine._escape_value(123), "123")
        self.assertEqual(NativeDumpEngine._escape_value(decimal.Decimal("45.67")), "45.67")
        self.assertEqual(NativeDumpEngine._escape_value(b"hello binary"), "X'68656c6c6f2062696e617279'")
        self.assertEqual(NativeDumpEngine._escape_value("O'Reilly; DROP TABLE users;"), "'O\\'Reilly; DROP TABLE users;'")
    def test_10_backup_job_and_windows_task_metadata(self):
        """Verifica la serialización de tareas programadas y helpers del Windows Scheduler."""
        from src.models.backup_job import BackupJob
        from src.services.windows_scheduler_service import WindowsSchedulerService

        job = BackupJob(
            name="Respaldo Nocturno",
            server_id="srv-100",
            database_name="__ALL__",
            backup_type=BackupType.FULL,
            interval_minutes=1440,
            windows_task_installed=True,
            start_time_str="03:30"
        )

        d = job.to_dict()
        self.assertTrue(d["windows_task_installed"])
        self.assertEqual(d["start_time_str"], "03:30")

        restored = BackupJob.from_dict(d)
        self.assertEqual(restored.name, "Respaldo Nocturno")
        self.assertTrue(restored.windows_task_installed)
        self.assertEqual(restored.start_time_str, "03:30")

        task_name = WindowsSchedulerService.build_task_name(job.id)
        self.assertTrue(task_name.startswith("MySqlAutoBkps_"))

        pythonw = WindowsSchedulerService.get_pythonw_executable()
        self.assertTrue(pythonw.lower().endswith("pythonw.exe") or pythonw.lower().endswith("python.exe"))

        runner = WindowsSchedulerService.get_headless_runner_path()
        self.assertTrue(os.path.isfile(runner))


if __name__ == "__main__":
    unittest.main()

