import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestAlembicWorkflowIntegration:
    """Integration tests for complete Alembic workflow."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary directory for test project."""
        temp_dir = tempfile.mkdtemp()
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        yield Path(temp_dir)
        os.chdir(original_dir)
        shutil.rmtree(temp_dir)

    def run_mitsuki_init(self, project_name, temp_dir):
        """Helper to run mitsuki init command."""
        inputs = f"{project_name}\nTest app\nsqlite\ny\nPost\nn\ny\n"
        result = subprocess.run(
            ["python3", "-m", "mitsuki.cli.bootstrap", "init"],
            input=inputs,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result

    def test_full_workflow_default_profile(self, temp_project):
        """Test complete Alembic workflow with default profile (app.db)."""
        project_name = "test_app"

        # 1. Create project with Alembic
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0
        assert "Alembic configured" in result.stdout

        project_dir = temp_project / project_name
        assert project_dir.exists()
        assert (project_dir / "alembic").exists()
        assert (project_dir / "alembic.ini").exists()
        assert (project_dir / "alembic" / "env.py").exists()

        os.chdir(project_dir)

        # 2. Generate migration
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "initial"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Generating" in result.stdout

        # Check migration file was created
        versions_dir = project_dir / "alembic" / "versions"
        migration_files = list(versions_dir.glob("*_initial.py"))
        assert len(migration_files) == 1

        # Check migration content has GUID import
        migration_content = migration_files[0].read_text()
        assert "from mitsuki.data.adapters.sqlalchemy import GUID" in migration_content
        assert "GUID()" in migration_content

        # 3. Apply migration
        result = subprocess.run(
            ["alembic", "upgrade", "head"], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        assert "Running upgrade" in result.stderr

        # 4. Verify database was created with correct schema
        db_path = project_dir / "app.db"
        assert db_path.exists()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check posts table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is not None

        # Check posts table schema
        cursor.execute("PRAGMA table_info(posts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        assert "id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        # Check alembic_version table
        cursor.execute("SELECT version_num FROM alembic_version")
        version = cursor.fetchone()
        assert version is not None

        conn.close()

    def test_workflow_with_dev_profile(self, temp_project):
        """Test Alembic workflow using dev profile (dev.db)."""
        project_name = "test_dev_app"

        # Create project
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        # Generate and apply migration with dev profile
        env = os.environ.copy()
        env["MITSUKI_PROFILE"] = "dev"

        # Generate migration
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "dev_initial"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        # Apply migration
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

        # Verify dev.db was created
        db_path = project_dir / "dev.db"
        assert db_path.exists()

        # Verify app.db was NOT created (since we used dev profile)
        app_db_path = project_dir / "app.db"
        assert not app_db_path.exists()

        # Verify schema in dev.db
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_invalid_profile_fails_fast(self, temp_project):
        """Test that invalid profile name fails with clear error."""
        project_name = "test_invalid_profile"

        # Create project
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        # Try to use invalid profile
        env = os.environ.copy()
        env["MITSUKI_PROFILE"] = "invalid"

        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "test"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should fail with helpful error
        assert result.returncode != 0
        assert "FileNotFoundError" in result.stderr
        assert "application-invalid.yml" in result.stderr
        assert "Available profiles" in result.stderr

    def test_multiple_migrations(self, temp_project):
        """Test applying multiple migrations in sequence."""
        project_name = "test_multi_migration"

        # Create project
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        # First migration
        subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "first"],
            capture_output=True,
            timeout=30,
        )
        subprocess.run(["alembic", "upgrade", "head"], capture_output=True, timeout=30)

        # Second migration (simulate schema change)
        subprocess.run(
            ["alembic", "revision", "-m", "second"], capture_output=True, timeout=30
        )
        result = subprocess.run(
            ["alembic", "upgrade", "head"], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0

        # Check both migrations in history
        result = subprocess.run(
            ["alembic", "history"], capture_output=True, text=True, timeout=30
        )
        assert "first" in result.stdout
        assert "second" in result.stdout

    def test_downgrade_migration(self, temp_project):
        """Test downgrading migrations."""
        project_name = "test_downgrade"

        # Create project and apply migration
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "create_posts"],
            capture_output=True,
            timeout=30,
        )
        subprocess.run(["alembic", "upgrade", "head"], capture_output=True, timeout=30)

        # Verify table exists
        db_path = project_dir / "app.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is not None
        conn.close()

        # Downgrade
        result = subprocess.run(
            ["alembic", "downgrade", "base"], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0

        # Verify table was dropped
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
        )
        assert cursor.fetchone() is None
        conn.close()

    def test_profile_switching_uses_different_databases(self, temp_project):
        """Test that switching profiles uses different databases."""
        project_name = "test_profile_switch"

        # Create project
        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        # Apply to default database
        subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "initial"],
            capture_output=True,
            timeout=30,
        )
        subprocess.run(["alembic", "upgrade", "head"], capture_output=True, timeout=30)

        # Apply to dev database
        env = os.environ.copy()
        env["MITSUKI_PROFILE"] = "dev"
        subprocess.run(
            ["alembic", "upgrade", "head"], env=env, capture_output=True, timeout=30
        )

        # Both databases should exist
        assert (project_dir / "app.db").exists()
        assert (project_dir / "dev.db").exists()

        # Both should have posts table
        for db_name in ["app.db", "dev.db"]:
            conn = sqlite3.connect(project_dir / db_name)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='posts'"
            )
            assert cursor.fetchone() is not None
            conn.close()

    def test_domain_init_exports_entities(self, temp_project):
        """Test that generated domain/__init__.py exports entities for Alembic."""
        project_name = "test_exports"

        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        domain_init = project_dir / project_name / "src" / "domain" / "__init__.py"

        assert domain_init.exists()
        content = domain_init.read_text()

        assert "from .post import Post" in content
        assert content.strip()  # Not empty

    def test_metadata_populated_via_domain_import(self, temp_project):
        """Test that importing from domain package populates entity registry."""
        project_name = "test_import"

        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        result = subprocess.run(
            [
                "python3",
                "-c",
                "from test_import.src.domain import *; "
                "from mitsuki.data.entity import _entity_registry; "
                "print('Entities:', len(_entity_registry))",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "Entities: 1" in result.stdout

    def test_alembic_detects_tables_after_domain_import(self, temp_project):
        """Test that Alembic can detect tables after importing domain."""
        project_name = "test_detection"

        result = self.run_mitsuki_init(project_name, temp_project)
        assert result.returncode == 0

        project_dir = temp_project / project_name
        os.chdir(project_dir)

        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "detect_tables"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "Detected added table 'posts'" in result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
