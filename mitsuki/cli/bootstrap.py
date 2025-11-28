from pathlib import Path

import click

from mitsuki.core.enums import DatabaseDialect
from mitsuki.core.logging import get_logger

logger = get_logger()


def read_template(template_name: str) -> str:
    """Read a template file from the templates directory."""
    template_dir = Path(__file__).parent / "templates"
    template_path = template_dir / template_name
    return template_path.read_text()


def create_directory(path: Path) -> None:
    """Create a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {path}")


def write_file(path: Path, content: str) -> None:
    """Write content to a file."""
    path.write_text(content)
    logger.info(f"Created file: {path}")


def create_domain_files(app_dir: Path, app_name: str, domain_name: str) -> None:
    """Create entity, repository, service, and controller for a domain."""
    domain_lower = domain_name.lower()

    # Entity
    entity_content = read_template("entity.py.tpl").replace(
        "{{DOMAIN_NAME}}", domain_name
    )
    write_file(app_dir / "domain" / f"{domain_lower}.py", entity_content)

    # Repository
    repo_content = (
        read_template("repository.py.tpl")
        .replace("{{DOMAIN_NAME}}", domain_name)
        .replace("{{domain_name}}", domain_lower)
    )
    write_file(app_dir / "repository" / f"{domain_lower}_repository.py", repo_content)

    # Service
    service_content = (
        read_template("service.py.tpl")
        .replace("{{DOMAIN_NAME}}", domain_name)
        .replace("{{domain_name}}", domain_lower)
    )
    write_file(app_dir / "service" / f"{domain_lower}_service.py", service_content)

    # Controller
    controller_content = (
        read_template("controller.py.tpl")
        .replace("{{DOMAIN_NAME}}", domain_name)
        .replace("{{domain_name}}", domain_lower)
    )
    write_file(
        app_dir / "controller" / f"{domain_lower}_controller.py", controller_content
    )


@click.group()
def cli():
    pass


@cli.command()
def init():
    """Bootstrap a new Mitsuki application."""

    # Application name
    app_name = click.prompt("Application name")
    app_name = app_name.lower().replace("-", "_").replace(" ", "_")

    # Description
    description = click.prompt("Description (optional)", default="", show_default=False)

    # Database type
    db_type = click.prompt(
        "Database type",
        type=click.Choice(["sqlite", "postgresql", "mysql"], case_sensitive=False),
        default="sqlite",
    )

    # Starter domain
    create_domain = click.confirm(
        "Create starter domain (i.e. models/object definitions)?", default=True
    )

    domains = []
    if create_domain:
        domain_name = click.prompt("Domain name (e.g., User, Product)")
        domains.append(domain_name)

        # Additional domains
        while click.confirm("Add another domain object?", default=False):
            domain_name = click.prompt("Domain name")
            domains.append(domain_name)

    # Alembic setup
    setup_alembic = click.confirm(
        "Setup Alembic for database migrations?", default=True
    )

    # Create project structure
    project_root = Path.cwd() / app_name
    package_dir = project_root / app_name
    src_dir = package_dir / "src"
    app_dir = src_dir

    if project_root.exists():
        click.echo(f"Error: Directory {app_name} already exists")
        return

    # Create directories
    create_directory(project_root)
    create_directory(package_dir)
    create_directory(src_dir)

    subdirs = ["domain", "repository", "service", "controller"]
    init_content = read_template("__init__.py.tpl").replace(
        "{{MODULE_DESCRIPTION}}", description or f"{app_name} module"
    )

    for subdir in subdirs:
        create_directory(app_dir / subdir)
        write_file(app_dir / subdir / "__init__.py", init_content)

    write_file(app_dir / "__init__.py", init_content)

    # Create app.py with controller imports
    controller_imports = ""
    if domains:
        imports = []
        for domain_name in domains:
            domain_lower = domain_name.lower()
            imports.append(
                f"from {app_name}.src.controller.{domain_lower}_controller import {domain_name}Controller"
            )
        controller_imports = "\n" + "\n".join(imports)

    app_content = read_template("app.py.tpl").replace(
        "{{CONTROLLER_IMPORT}}", controller_imports
    )
    write_file(src_dir / "app.py", app_content)

    # Create __init__.py files for package structure
    write_file(package_dir / "__init__.py", "")
    write_file(src_dir / "__init__.py", "")

    # Create domain files
    for domain_name in domains:
        create_domain_files(app_dir, app_name, domain_name)

    # Update domain/__init__.py to export all entities for Alembic
    if domains:
        domain_exports = "\n".join(
            [
                f"from .{domain_name.lower()} import {domain_name}"
                for domain_name in domains
            ]
        )
        domain_init = (
            f'"""{description or f"{app_name} domain entities"}"""\n{domain_exports}\n'
        )
        write_file(app_dir / "domain" / "__init__.py", domain_init)

    # Create configuration files
    db_url_map = {
        "sqlite": f"sqlite:///{app_name}.db",
        "postgresql": f"postgresql://localhost/{app_name}",
        "mysql": f"mysql://localhost/{app_name}",
    }
    db_url = db_url_map[db_type]

    app_yml = read_template("application.yml.tpl").replace("{{app_name}}", app_name)
    app_yml = app_yml.replace("sqlite:///{{app_name}}.db", db_url)
    write_file(project_root / "application.yml", app_yml)

    for env in ["dev", "stg", "prod"]:
        env_yml = read_template(f"application-{env}.yml.tpl").replace(
            "{{app_name}}", app_name
        )
        if db_type == DatabaseDialect.SQLITE:
            env_yml = env_yml.replace(
                "postgresql://localhost/{{app_name}}", f"sqlite:///{app_name}.db"
            )
        elif db_type == DatabaseDialect.MYSQL:
            env_yml = env_yml.replace("postgresql://localhost/", "mysql://localhost/")
        write_file(project_root / f"application-{env}.yml", env_yml)

    # Create README
    app_title = app_name.replace("_", " ").title()
    domain_section = ""

    if domains:
        endpoints = []
        for domain_name in domains:
            domain_lower = domain_name.lower()
            endpoints.append(f"""
- `GET /api/{domain_lower}` - List all {domain_lower}s
- `GET /api/{domain_lower}/{{id}}` - Get {domain_lower} by ID
- `POST /api/{domain_lower}` - Create new {domain_lower}
- `PUT /api/{domain_lower}/{{id}}` - Update {domain_lower}
- `DELETE /api/{domain_lower}/{{id}}` - Delete {domain_lower}""")

        domain_section = "\n## API Endpoints\n" + "\n".join(endpoints) + "\n"

    readme = (
        read_template("README.md.tpl")
        .replace("{{APP_TITLE}}", app_title)
        .replace("{{app_name}}", app_name)
        .replace("{{DOMAIN_SECTION}}", domain_section)
    )
    write_file(project_root / "README.md", readme)

    # Create .gitignore
    gitignore = read_template("gitignore.tpl")
    write_file(project_root / ".gitignore", gitignore)

    # Setup Alembic if requested
    if setup_alembic:
        alembic_dir = project_root / "alembic"
        versions_dir = alembic_dir / "versions"
        create_directory(alembic_dir)
        create_directory(versions_dir)

        # Create alembic.ini
        alembic_ini = read_template("alembic.ini.tpl")
        write_file(project_root / "alembic.ini", alembic_ini)

        # Create alembic/env.py
        alembic_env = read_template("alembic_env.py.tpl").replace(
            "{{app_name}}", app_name
        )
        write_file(alembic_dir / "env.py", alembic_env)

        # Create alembic/script.py.mako
        alembic_script = read_template("alembic_script.py.mako.tpl")
        write_file(alembic_dir / "script.py.mako", alembic_script)

        # Create empty __init__.py in versions
        write_file(versions_dir / "__init__.py", "")

        click.echo("\n✓ Alembic configured for database migrations")

    click.echo(f"\nSuccessfully created Mitsuki application: {app_name}")
    click.echo("\nTo get started:")
    click.echo(f"  cd {app_name}")
    click.echo(f"  python3 -m {app_name}.src.app")
    click.echo("\nOr with a specific profile:")
    click.echo(f"  MITSUKI_PROFILE=development python3 -m {app_name}.src.app")

    if setup_alembic:
        click.echo("\nTo create your first migration:")
        click.echo(f"  cd {app_name}")
        click.echo("  alembic revision --autogenerate -m 'initial schema'")
        click.echo("  alembic upgrade head")


def main():
    cli()


if __name__ == "__main__":
    # For running the bootstrap script as a script
    cli()
