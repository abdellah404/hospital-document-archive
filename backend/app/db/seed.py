from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import User


def seed_roles(db):
    roles = {}

    for role_name in ("ADMIN", "ARCHIVIST"):
        role = db.scalar(
            select(Role).where(
                Role.name == role_name
            )
        )

        if role is None:
            role = Role(
                name=role_name
            )

            db.add(role)
            db.flush()

            print(
                f"Created role '{role_name}'."
            )

        roles[role_name] = role

    return roles


def seed_admin(db, admin_role: Role):
    admin = db.scalar(
        select(User).where(
            User.username
            == settings.seed_admin_username
        )
    )

    if admin is not None:
        print(
            f"Admin user "
            f"'{settings.seed_admin_username}' "
            f"already exists."
        )
        return

    admin = User(
        username=settings.seed_admin_username,
        email=settings.seed_admin_email,
        password_hash=hash_password(
            settings.seed_admin_password
        ),
        role_id=admin_role.id,
        is_active=True,
    )

    db.add(admin)

    print(
        f"Created admin user "
        f"'{settings.seed_admin_username}'."
    )


def seed():
    db = SessionLocal()

    try:
        roles = seed_roles(db)

        seed_admin(
            db,
            roles["ADMIN"],
        )

        db.commit()

        print(
            "Database seeding completed successfully."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed()