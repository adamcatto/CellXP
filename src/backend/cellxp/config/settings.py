from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    product_name: str = "CellXP"
    environment: str = "development"
