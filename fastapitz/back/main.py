import jwt
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Annotated
from passlib.context import CryptContext
from fastapitz.back.database import setup_database, SessionDep, ResumeModel, select, UsersModel
from fastapitz.back.schemas import AddResumeSchema, ResumeSchema, UserSchema
from authx import AuthX, AuthXConfig
import uvicorn

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Настройка AuthX для JWT
config = AuthXConfig()
config.JWT_SECRET_KEY = 'SECRET_KEY'  # Замените на безопасный ключ в продакшене
config.JWT_ACCESS_COOKIE_NAME = 'access_token'
config.JWT_TOKEN_LOCATION = ['cookies']
config.JWT_COOKIE_CSRF_PROTECT = False
config.JWT_DECODE_ALGORITHMS = ["HS256"]

security = AuthX(config=config)

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fron-api.onrender.com", "https://fastapi-auth-crud-haf0.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



async def get_current_user(request: Request, session: SessionDep):
    try:
        token = request.cookies.get(config.JWT_ACCESS_COOKIE_NAME)
        if not token:
            raise HTTPException(status_code=401, detail="Токен не найден в cookies")
        
        try:
            payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Ошибка декодирования токена: {str(e)}")

        email = payload.get('sub')
        if not email:
            raise HTTPException(status_code=401, detail="Email не найден в токене")
        
        query = select(UsersModel).where(UsersModel.email == email)
        result = await session.execute(query)
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(status_code=401, detail=f"Пользователь с email {email} не найден")
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Ошибка авторизации: {str(e)}")

CurrentUserDep = Annotated[UsersModel, Depends(get_current_user)]

@app.post('/register', tags=["auth"])
async def register(cred: UserSchema, session: SessionDep):
    query = select(UsersModel).where(UsersModel.email == cred.email)
    result = await session.execute(query)
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    hashed_password = pwd_context.hash(cred.password)
    new_user = UsersModel(email=cred.email, password=hashed_password)
    session.add(new_user)
    await session.commit()
    return {"message": "Пользователь успешно зарегистрирован"}

@app.post('/login', tags=["auth"])
async def login(cred: UserSchema, response: Response, session: SessionDep):
    print(f"Login attempt: email={cred.email}, password={cred.password}")
    query = select(UsersModel).where(UsersModel.email == cred.email)
    result = await session.execute(query)
    user = result.scalars().first()
    
    if not user:
        print("User not found")
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    if not pwd_context.verify(cred.password, user.password):
        print("Password verification failed")
        raise HTTPException(status_code=401, detail="Неверный пароль")
    
    token = security.create_access_token(uid=user.email)
    print(f"Generated token: {token}")
    response.set_cookie(
        key=config.JWT_ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",  # ← Важно для кросс-домена!
        secure=True,      # ← True для HTTPS
        path="/",
    )
    print(f"Cookie set: {config.JWT_ACCESS_COOKIE_NAME}={token}")
    return {"access_token": token}

@app.get("/me", tags=["auth"])
async def get_me(current_user: CurrentUserDep):
    return {"email": current_user.email, "id": current_user.id}

@app.on_event("startup")
async def on_startup():
    await setup_database()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Resume API!"}

@app.post('/resumes', tags=["resumes"])
async def add_resume(data: AddResumeSchema, session: SessionDep, current_user: CurrentUserDep):
    print(f"Adding resume: title={data.title}, user_id={current_user.id}")
    new_resume = ResumeModel(
        title=data.title,
        context=data.context,
        user_id=current_user.id
    )
    session.add(new_resume)
    await session.commit()
    print("Resume added successfully")
    return {'ok': True}

@app.get('/resumes', tags=["resumes"])
async def get_resume(session: SessionDep, current_user: CurrentUserDep):
    query = select(ResumeModel).where(ResumeModel.user_id == current_user.id)
    response = await session.execute(query)
    resumes = response.scalars().all()
    print(f"Retrieved {len(resumes)} resumes for user_id={current_user.id}")
    return resumes

@app.get('/resumes/{resume_id}', tags=["resumes"])
async def get_one_resume(resume_id: int, session: SessionDep, current_user: CurrentUserDep):
    query = select(ResumeModel).where(ResumeModel.id == resume_id, ResumeModel.user_id == current_user.id)
    result = await session.execute(query)
    resume = result.scalars().first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено или не принадлежит пользователю")
    
    print(f"Retrieved resume: id={resume.id}, title={resume.title}")
    return resume

@app.put('/resumes/{resume_id}', tags=["resumes"])
async def update_resume(resume_id: int, data: AddResumeSchema, session: SessionDep, current_user: CurrentUserDep):
    query = select(ResumeModel).where(ResumeModel.id == resume_id, ResumeModel.user_id == current_user.id)
    result = await session.execute(query)
    resume = result.scalars().first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено или не принадлежит пользователю")
    
    print(f"Updating resume: id={resume_id}, new_title={data.title}")
    resume.title = data.title
    resume.context = data.context
    await session.commit()
    print("Resume updated successfully")
    return {'ok': True}

@app.delete('/resumes/{resume_id}', tags=["resumes"])
async def delete_resume(resume_id: int, session: SessionDep, current_user: CurrentUserDep):
    query = select(ResumeModel).where(ResumeModel.id == resume_id, ResumeModel.user_id == current_user.id)
    result = await session.execute(query)
    resume = result.scalars().first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено или не принадлежит пользователю")
    
    print(f"Deleting resume: id={resume_id}")
    await session.delete(resume)
    await session.commit()
    print("Resume deleted successfully")
    return {'ok': True}

@app.post('/resumes/{resume_id}/improve', tags=["resumes"])
async def improve_resume(resume_id: int, session: SessionDep, current_user: CurrentUserDep):
    query = select(ResumeModel).where(ResumeModel.id == resume_id, ResumeModel.user_id == current_user.id)
    result = await session.execute(query)
    resume = result.scalars().first()
    
    if not resume:
        raise HTTPException(status_code=404, detail="Резюме не найдено или не принадлежит пользователю")
    
    print(f"Improving resume: id={resume_id}, original_context={resume.context}")
    resume.context = resume.context + " [Improved]"
    await session.commit()
    print(f"Resume improved: id={resume_id}, new_context={resume.context}")
    return {"ok": True, "improved_context": resume.context}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
