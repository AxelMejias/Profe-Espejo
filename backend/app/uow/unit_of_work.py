from sqlmodel import Session
from app.database import engine


class UnitOfWork:
    """
    Patrón Unit of Work: encapsula el ciclo de vida de la sesión.
    Hace commit automático al salir del bloque `with` si no hubo excepciones,
    o rollback si ocurrió algún error.

    Uso:
        with UnitOfWork() as uow:
            resultado = some_service.create(uow.session, data)
    """

    def __init__(self):
        self.session: Session = Session(engine)

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
