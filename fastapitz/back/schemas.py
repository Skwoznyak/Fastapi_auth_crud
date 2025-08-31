from pydantic import BaseModel, EmailStr

class AddResumeSchema(BaseModel):
    title: str
    context: str

class ResumeSchema(AddResumeSchema):
    id: int

class UserSchema(BaseModel):
    email: EmailStr  # Проверяет, что это валидный email
    password: str

class AddUserSchema(UserSchema):
    id: int