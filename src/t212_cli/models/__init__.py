from pydantic import BaseModel, ConfigDict


class T212Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class AccountSummary(T212Model):
    id: int
    currency: str
    totalValue: float
