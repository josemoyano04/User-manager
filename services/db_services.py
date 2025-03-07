import os
import asyncio
import libsql_client as libsql
from libsql_client import Client
from models.user_db import User, UserDB
from dotenv import load_dotenv, find_dotenv
from typing import Union

# Lectura de .env
DOTENV_URL = find_dotenv("../.env")
load_dotenv(DOTENV_URL)

# Obtención de datos para conectar a la base de datos
DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_AUTH_TOKEN = os.getenv("DATABASE_AUTH_TOKEN")

# Cliente con conexión a la base de datos
async def create_client() -> Client:
    """
    Crea un cliente para conectarse a la base de datos.

    Returns:
        Client: Un cliente de libsql configurado con la URL y el token de autenticación de la base de datos.
    """
    return libsql.create_client(url=DATABASE_URL, auth_token=DATABASE_AUTH_TOKEN)

# Bloqueo para controlar concurrencia de conexiones.
look = asyncio.locks.Lock()

# Operaciones CRUD

async def add_user(client: Client, user: UserDB) -> None:
    """
    Agrega un nuevo usuario a la base de datos.

    Args:
        client (Client): El cliente de la base de datos.
        user (UserDB): El objeto UserDB que contiene la información del usuario a agregar.
    """
    try:
        async with look:
            await client.execute(
                "INSERT INTO user(full_name, username, email, hashed_password) VALUES (?, ?, ?, ?);",
                [*user.model_dump().values()]
            )
    finally:
        await client.close()
        

async def get_user(client: Client, username: str, hidden_password: bool = False) -> Union[User, UserDB, None]:
    """
    Obtiene un usuario de la base de datos a partir de su nombre de usuario.

    Args:
        client (Client): El cliente de la base de datos.
        username (str): El nombre de usuario del usuario a buscar.
        hidden_password (bool): Flag para indicar si retornar el hashed_password del usuario.
    Returns:
        Union[User, UserDB, None]: Un objeto User si se encuentra el usuario, de lo contrario None y UserDB si hidden_password es True.
    """
    try:
        async with look:
            result = await client.execute("""SELECT full_name, username, email, hashed_password
                                        FROM user WHERE username = ?;""", [username])
            
            row = result.rows[0] if len(result.rows) == 1 else None #TODO mejorar logica de recuperacion de usuario.
            
            if row:
                user_data = {"full_name": row[0], "username": row[1], "email": row[2]}
                if hidden_password:
                    user_data["password"] = row[3]
                    return UserDB(**user_data)
                
                return User(**user_data)
            return None
    finally:
        await client.close()


async def delete_user(client: Client, username: str) -> None:
    """
    Elimina un usuario de la base de datos a partir de su nombre de usuario.

    Args:
        client (Client): El cliente de la base de datos.
        username (str): El nombre de usuario del usuario a eliminar.
    """
    try:
        async with look:
            await client.execute("DELETE FROM user WHERE username = ?", [username])
    finally:
        await client.close()
        
async def update_user(client: Client, username: str, updated_user: UserDB) -> None:
    """
    Actualiza la información de un usuario en la base de datos.

    Args:
        client (Client): El cliente de la base de datos.
        username (str): El nombre de usuario del usuario a actualizar.
        updated_user (UserDB): El objeto UserDB que contiene la nueva información del usuario.
    """
    try:
        async with look:
            await client.execute(
                """UPDATE user
                SET full_name = ?, username = ?, email = ?, hashed_password = ?
                WHERE username = ?""",
                [updated_user.full_name, updated_user.username, updated_user.email,
                updated_user.password, username]
            )
    finally:
        await client.close()
        
async def exists_username(client: Client, username: str) -> bool:
    """
    Verifica si el nombre de usuario exista en la base de datos.

    Args:
        client (Client): Una instancia del cliente de base de datos que se utilizará para ejecutar la consulta.
        username (str): Nombre de usuario a validar.

    Returns:
        bool: Devuelve True si el nombre de usuario existe en la base de datos,
              de lo contrario, devuelve False.
    """
    try:
        async with look:
            result = await client.execute("SELECT * FROM user WHERE username = ?;", [username])
            
            return len(result.rows) != 0 
    finally:
        await client.close()
        
async def is_unique(client: Client, user: User, for_update_user: bool = False) -> bool:
    async with look:
        """
        Verifica la existencia de un usuario en la base de datos basado en el nombre de usuario y el correo electrónico.

        Args:
            client (Client): Una instancia del cliente de base de datos que se utilizará para ejecutar la consulta.
            user (User): Un objeto que contiene el nombre de usuario y el correo electrónico a verificar.
            for_update_user (bool): Un indicador que determina si se está verificando para actualizar un usuario existente. Si se indica como 'True',
                se ajusta la consulta para aceptar al menos una fila, la cual es resultante del usuario existente a actualizar.

        Returns:
            bool: Devuelve True si el nombre de usuario y el correo electrónico son únicos (no existen en la base de datos)
                cuando `for_update_user` es False, o si existe exactamente un usuario cuando `for_update_user` es True.
                Devuelve False en caso contrario.
        """
        try:
            result = await client.execute("SELECT * FROM user WHERE username = ? OR email = ?;", 
                                        [user.username, user.email])
            
            return len(result.rows) == 0 if not for_update_user else len(result.rows) == 1
        finally:
            await client.close()
