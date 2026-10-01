"""
Unit tests for the `mitsuki init` scaffolding CLI.
"""

import pytest
from click.testing import CliRunner

from mitsuki.cli.bootstrap import (
    cli,
    create_directory,
    create_domain_files,
    init,
    read_template,
    write_file,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Run each CLI invocation inside an empty temporary directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestFilesystemHelpers:
    """Tests for the small filesystem helpers."""

    def test_read_template(self):
        assert "{{DOMAIN_NAME}}" in read_template("entity.py.tpl")

    def test_create_directory_is_idempotent(self, tmp_path):
        target = tmp_path / "a" / "b"

        create_directory(target)
        create_directory(target)

        assert target.is_dir()

    def test_write_file(self, tmp_path):
        target = tmp_path / "out.txt"

        write_file(target, "hello")

        assert target.read_text() == "hello"


class TestCreateDomainFiles:
    """Tests for the four-file domain scaffold."""

    @pytest.fixture
    def app_dir(self, tmp_path):
        """`init` creates the layer directories before scaffolding."""
        for subdir in ("domain", "repository", "service", "controller"):
            (tmp_path / subdir).mkdir()
        return tmp_path

    def test_creates_all_four_layers(self, app_dir):
        create_domain_files(app_dir, "myapp", "Product")

        assert (app_dir / "domain" / "product.py").exists()
        assert (app_dir / "repository" / "product_repository.py").exists()
        assert (app_dir / "service" / "product_service.py").exists()
        assert (app_dir / "controller" / "product_controller.py").exists()

    def test_templates_render_domain_name(self, app_dir):
        create_domain_files(app_dir, "myapp", "Product")

        assert "Product" in (app_dir / "domain" / "product.py").read_text()

    def test_templates_render_lowercase_domain_name(self, app_dir):
        create_domain_files(app_dir, "myapp", "Product")

        assert (
            "{{domain_name}}"
            not in (app_dir / "repository" / "product_repository.py").read_text()
        )

    def test_no_unrendered_placeholders(self, app_dir):
        create_domain_files(app_dir, "myapp", "Product")

        for path in app_dir.rglob("*.py"):
            assert "{{DOMAIN_NAME}}" not in path.read_text()
            assert "{{domain_name}}" not in path.read_text()


class TestInitProjectStructure:
    """Tests for the generated project layout."""

    def test_app_name_is_normalized(self, runner, workspace):
        result = runner.invoke(init, input="My-App Name\n\nsqlite\nn\nn\n")

        assert result.exit_code == 0
        assert (workspace / "my_app_name").is_dir()

    def test_package_tree_created(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        package = workspace / "myapp" / "myapp" / "src"

        assert (package / "app.py").exists()
        assert (package / "__init__.py").exists()
        for subdir in ("domain", "repository", "service", "controller"):
            assert (package / subdir / "__init__.py").exists()

    def test_existing_directory_aborts(self, runner, workspace):
        (workspace / "myapp").mkdir()

        result = runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert "already exists" in result.output
        assert not (workspace / "myapp" / "myapp").exists()

    def test_submodule_init_gets_description(self, runner, workspace):
        runner.invoke(init, input="myapp\nMy cool app\nsqlite\nn\nn\n")

        init_py = (
            workspace / "myapp" / "myapp" / "src" / "domain" / "__init__.py"
        ).read_text()

        assert "My cool app" in init_py

    def test_empty_description_falls_back_to_app_name(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        init_py = (
            workspace / "myapp" / "myapp" / "src" / "domain" / "__init__.py"
        ).read_text()

        assert "myapp module" in init_py

    def test_app_py_imports_starter_controllers(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\ny\nUser\nn\nn\n")

        app_py = (workspace / "myapp" / "myapp" / "src" / "app.py").read_text()

        assert "from myapp.src.controller.user_controller import UserController" in (
            app_py
        )
        assert "Successfully created" in result.output

    def test_no_controller_imports_without_domains(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        app_py = (workspace / "myapp" / "myapp" / "src" / "app.py").read_text()

        assert "controller" not in app_py


class TestInitDomains:
    """Tests for optional starter domain scaffolding."""

    def test_single_domain(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\ny\nUser\nn\nn\n")

        package = workspace / "myapp" / "myapp" / "src"

        assert (package / "domain" / "user.py").exists()
        assert (package / "controller" / "user_controller.py").exists()

    def test_multiple_domains(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\ny\nUser\ny\nProduct\nn\nn\n")

        package = workspace / "myapp" / "myapp" / "src"

        assert (package / "domain" / "user.py").exists()
        assert (package / "domain" / "product.py").exists()

    def test_domain_init_exports_every_entity(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\ny\nUser\ny\nProduct\nn\nn\n")

        domain_init = (
            workspace / "myapp" / "myapp" / "src" / "domain" / "__init__.py"
        ).read_text()

        assert "from .user import User" in domain_init
        assert "from .product import Product" in domain_init


class TestInitConfiguration:
    """Tests for generated configuration files."""

    def test_application_yml(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert (workspace / "myapp" / "application.yml").exists()

    def test_profile_yml_files(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        root = workspace / "myapp"

        for env in ("dev", "stg", "prod"):
            assert (root / f"application-{env}.yml").exists()

    def test_sqlite_url_rewritten(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        content = (workspace / "myapp" / "application.yml").read_text()

        assert "sqlite:///myapp.db" in content
        assert "{{app_name}}" not in content

    def test_postgresql_url(self, runner, workspace):
        runner.invoke(init, input="myapp\n\npostgresql\nn\nn\n")

        content = (workspace / "myapp" / "application.yml").read_text()

        assert "postgresql://localhost/myapp" in content

    def test_mysql_url(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nmysql\nn\nn\n")

        content = (workspace / "myapp" / "application.yml").read_text()

        assert "mysql://localhost/myapp" in content

    def test_sqlite_profiles_use_profile_scoped_db_files(self, runner, workspace):
        """Each profile gets its own .db file, named after the profile."""

        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        root = workspace / "myapp"

        for env in ("dev", "stg", "prod"):
            content = (root / f"application-{env}.yml").read_text()
            assert f"sqlite:///myapp_{env}.db" in content

    def test_mysql_profiles_use_mysql_url(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nmysql\nn\nn\n")

        content = (workspace / "myapp" / "application-dev.yml").read_text()

        assert "mysql://localhost/" in content
        assert "postgresql://localhost/" not in content

    def test_postgresql_profiles_unchanged(self, runner, workspace):
        runner.invoke(init, input="myapp\n\npostgresql\nn\nn\n")

        content = (workspace / "myapp" / "application-dev.yml").read_text()

        assert "postgresql://localhost/myapp" in content

    def test_no_unrendered_placeholders_in_any_config(self, runner, workspace):
        runner.invoke(init, input="myapp\n\npostgresql\nn\nn\n")

        root = workspace / "myapp"

        for path in list(root.glob("application*.yml")):
            assert "{{app_name}}" not in path.read_text()


class TestInitDocs:
    """Tests for the generated README and gitignore."""

    def test_readme_created(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert (workspace / "myapp" / "README.md").exists()

    def test_readme_title_from_app_name(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert "Myapp" in (workspace / "myapp" / "README.md").read_text()

    def test_readme_documents_domain_endpoints(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\ny\nUser\nn\nn\n")

        readme = (workspace / "myapp" / "README.md").read_text()

        assert "## API Endpoints" in readme
        assert "GET /api/user" in readme
        assert "POST /api/user" in readme
        assert "DELETE /api/user/{id}" in readme

    def test_readme_omits_endpoint_section_without_domains(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        readme = (workspace / "myapp" / "README.md").read_text()

        assert "## API Endpoints" not in readme
        assert "{{DOMAIN_SECTION}}" not in readme

    def test_gitignore_created(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert (workspace / "myapp" / ".gitignore").exists()


class TestInitAlembic:
    """Tests for optional Alembic scaffolding."""

    def test_creates_alembic_tree(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\nn\ny\n")

        root = workspace / "myapp"

        assert (root / "alembic.ini").exists()
        assert (root / "alembic" / "env.py").exists()
        assert (root / "alembic" / "script.py.mako").exists()
        assert (root / "alembic" / "versions" / "__init__.py").exists()
        assert "Alembic configured" in result.output

    def test_env_py_renders_app_name(self, runner, workspace):
        runner.invoke(init, input="myapp\n\nsqlite\nn\ny\n")

        env_py = (workspace / "myapp" / "alembic" / "env.py").read_text()

        assert "{{app_name}}" not in env_py
        assert "myapp" in env_py

    def test_skipped_when_declined(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert not (workspace / "myapp" / "alembic").exists()
        assert "Alembic configured" not in result.output

    def test_migration_instructions_shown(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\nn\ny\n")

        assert "alembic revision --autogenerate" in result.output


class TestInitOutput:
    """Tests for the CLI's closing instructions."""

    def test_next_steps_shown(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert "cd myapp" in result.output
        assert "python3 -m myapp.src.app" in result.output

    def test_success_message(self, runner, workspace):
        result = runner.invoke(init, input="myapp\n\nsqlite\nn\nn\n")

        assert "Successfully created Mitsuki application: myapp" in result.output


class TestCliGroup:
    """Tests for the top-level command group."""

    def test_init_is_registered(self):
        assert "init" in cli.commands

    def test_grafana_dashboard_is_registered(self):
        assert "grafana-dashboard" in cli.commands

    def test_help_lists_commands(self, runner):
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "grafana-dashboard" in result.output


class TestGeneratedProjectImports:
    """The generated app must be importable, not just well-formed text."""

    def test_generated_app_module_is_valid_python(self, runner, workspace):
        runner.invoke(init, input="myapp\nDesc\nsqlite\ny\nUser\nn\nn\n")

        app_py = workspace / "myapp" / "myapp" / "src" / "app.py"

        compile(app_py.read_text(), str(app_py), "exec")

    def test_generated_domain_modules_are_valid_python(self, runner, workspace):
        runner.invoke(init, input="myapp\nDesc\nsqlite\ny\nUser\nn\nn\n")

        package = workspace / "myapp" / "myapp" / "src"

        for path in package.rglob("*.py"):
            compile(path.read_text(), str(path), "exec")

    def test_generated_yaml_parses(self, runner, workspace):
        import yaml

        runner.invoke(init, input="myapp\nDesc\nsqlite\nn\nn\n")

        for path in (workspace / "myapp").glob("application*.yml"):
            assert isinstance(yaml.safe_load(path.read_text()), dict)

    def test_generated_project_uses_path_relative_paths(self, runner, workspace):
        """Generated files must not embed absolute build-machine paths."""

        runner.invoke(init, input="myapp\nDesc\nsqlite\ny\nUser\nn\nn\n")

        root = workspace / "myapp"

        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if ".db" in path.name:
                continue
            assert str(workspace) not in path.read_text(errors="ignore"), path


class TestGrafanaDashboardCommand:
    """Tests for the grafana-dashboard command."""

    def test_writes_dashboard_to_directory(self, runner, tmp_path):
        from mitsuki.grafana import DASHBOARD_FILENAME

        result = runner.invoke(cli, ["grafana-dashboard", "-o", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / DASHBOARD_FILENAME).exists()
        assert "Wrote Grafana dashboard" in result.output

    def test_writes_dashboard_to_file(self, runner, tmp_path):
        target = tmp_path / "custom.json"

        result = runner.invoke(cli, ["grafana-dashboard", "-o", str(target)])

        assert result.exit_code == 0
        assert target.exists()
