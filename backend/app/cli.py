"""Platforma CLI. Provisioning superuser-DSN bilan yuradi (platforma-amali):

    python -m app.cli provision-tenant --name "Demo Tashkilot" --slug demo \
        --owner-phone +998901234567
"""

import asyncio

import typer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.modules.tenancy.service import provision_tenant

cli = typer.Typer(help="Employee Control — platforma boshqaruv buyruqlari")


@cli.callback()
def _root():
    """Bitta buyruq bo'lsa ham subcommand-rejimni majburlash uchun callback."""


def _admin_sessionmaker():
    url = get_settings().migrations_database_url.replace("+psycopg", "+asyncpg")
    engine = create_async_engine(url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@cli.command("provision-tenant")
def provision_tenant_cmd(
    name: str = typer.Option(..., help="Tashkilot nomi"),
    slug: str = typer.Option(..., help="Unikal slug (kichik harf, chiziqcha)"),
    owner_phone: str = typer.Option(..., help="Org-admin telefon raqami"),
    owner_name: str = typer.Option("Org Admin", help="Org-admin ismi"),
):
    async def run():
        engine, maker = _admin_sessionmaker()
        try:
            async with maker() as session:
                async with session.begin():
                    result = await provision_tenant(
                        session,
                        name=name,
                        slug=slug,
                        owner_phone=owner_phone,
                        owner_name=owner_name,
                    )
            # ASCII — Windows-konsollar (cp1251) unicode-belgilarni ko'tarmaydi
            if result.created:
                typer.echo(f"[OK] Tenant yaratildi: {result.org.name} ({result.org.id})")
                typer.echo(f"  Owner: {result.owner.full_name} {result.owner.phone}")
                typer.echo(f"  Aktivatsiya-token (bir marta ko'rsatiladi): {result.invite_token}")
                typer.echo(f"  Qo'lda teriladigan kod: {result.invite_code}")
            else:
                typer.echo(f"[i] Tenant allaqachon mavjud: {result.org.name} ({result.org.id})")
        finally:
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    cli()
