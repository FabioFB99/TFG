# TFG2/Back/crud/__init__.py

from .crud_user import (
    authenticate_user, create_user_in_db, get_user_by_alias_from_db,
    update_user_in_db, delete_user_from_db
)
from .crud_coche import (
    create_coche_in_db, get_coche_by_id_from_db, get_all_coches_from_db,
    get_coches_by_user_id_from_db, update_coche_in_db, delete_coche_from_db
)