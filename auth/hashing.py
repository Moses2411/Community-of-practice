from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['pbkdf2_sha256'], deprecated = 'auto')

class Hash():
    @staticmethod
    def hash_password(password: str):
        return pwd_context.hash(password)
    @staticmethod
    def verify(hashed_password, plain_password):
        return pwd_context.verify(plain_password, hashed_password)