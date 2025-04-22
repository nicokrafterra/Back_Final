#-----------------------------------------------------------------------------------------
#Se realizan todas las importaciones necesarias
from typing import List, Optional
import bcrypt
from fastapi import FastAPI, APIRouter , Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from conexion import crear, get_db
from modelo import Base, TipoPlan, Usuario, Reserva, Pqr
from schemas import RespuestaPQR, UsuarioBase as cli
from schemas import ReservaU as usu
from schemas import Login 
from schemas import PQRS
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from fastapi.staticfiles import StaticFiles
from schemas import ActualizarContraseña
from passlib.context import CryptContext
from modelo import Plan
from schemas import PlanCreate, PlanResponse
from datetime import date
from auth import get_current_user,crear_token_jwt,verificar_token
from auth import generar_token_reset
from email_utils import send_reset_email
from schemas import EmailSchema
from auth import verificar_token
from schemas import ResetPasswordRequest
import logging
#-----------------------------------------------------------------------------------------
#Se inicializan

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = FastAPI()
router = APIRouter()
SECRET_KEY = "123456789"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
Base.metadata.create_all(bind=crear)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#-----------------------------------------------------------------------------------------

app.mount("/Imagenes", StaticFiles(directory="Imagenes"), name="Imagenes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[   "https://frontfinal-production.up.railway.app",
    "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"]
    
    )

@app.get("/")
def read_root():
    return {"mensaje": "¡Bienvenido al backend!"}

#-----------------------------------------------------------------------------------------
#Metodos de usuario

#Metodo de llamado a la base de datos para obtener los datos de eol usuario
@app.get("/usuarios/")
async def obtener_usuarios(db: Session = Depends(get_db)):
    usuarios = db.query(Usuario).all()
    return usuarios

#Metodo de creacion de nuevos usuarios
@app.post("/usuarios/", response_model=cli)
async def crear_usuario(usuario: cli, db: Session = Depends(get_db)):
    contraseña_encriptada = bcrypt.hashpw(usuario.contraseñaUsuario.encode('utf-8'), bcrypt.gensalt())
    
    nuevo_usuario = Usuario(
        nombre=usuario.nombre,
        correoElectronico=usuario.correoElectronico,
        contraseñaUsuario=contraseña_encriptada.decode('utf-8'),
        numeroCelular=usuario.numeroCelular,
        esAdmin=usuario.esAdmin
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

#Metodo para actualizacion de datos de el usuario
@app.put("/usuarios/{usuario_id}", response_model=cli)
async def actualizar_usuario(usuario_id: int, usuario_actualizado: cli, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    for key, value in usuario_actualizado.dict().items():
        setattr(usuario, key, value)

    db.commit()
    db.refresh(usuario)
    return usuario

#Metodo para eliminar el usuario
@app.delete("/usuarios/{usuario_id}", response_model=cli)
async def eliminar_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.delete(usuario)
    db.commit()
    return usuario

@app.get("/usuarios/me")
async def obtener_usuario_actual(usuario: Usuario = Depends(get_current_user)):
    return usuario

@app.post("/login")
async def login(user: Login, db: Session = Depends(get_db)):
    db_user = db.query(Usuario).filter(Usuario.correoElectronico == user.nombre_usuario).first()
    
    if db_user is None or not pwd_context.verify(user.password, db_user.contraseñaUsuario):
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = crear_token_jwt(usuario=db_user, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/usuarios/{user_id}/imagen")
async def subir_imagen_usuario(
    user_id: int,
    imagen: UploadFile = File(...),  
    db: Session = Depends(get_db)
):
    


    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")


    imagen_path = f"Imagenes/{imagen.filename}"
    os.makedirs(os.path.dirname(imagen_path), exist_ok=True)
    with open(imagen_path, "wb") as f:
        f.write(await imagen.read())


    usuario.imagen = imagen_path
    db.commit()
    db.refresh(usuario)

    return {"message": "Imagen actualizada exitosamente", "imagen_path": imagen_path}

@app.get("/usuarios/{usuario_id}/pqrs/respondidos", response_model=List[PQRS])
async def obtener_pqrs_respondidos(usuario_id: int, db: Session = Depends(get_db)):
    pqrs_respondidos = db.query(Pqr).filter(Pqr.usuario_id == usuario_id, Pqr.respuesta != None).all()
    if not pqrs_respondidos:
        raise HTTPException(status_code=404, detail="No se encontraron PQRs respondidos para este usuario")
    return pqrs_respondidos
from fastapi import Body

@app.put("/usuarios/{usuario_id}/correo", response_model=cli)
async def actualizar_correo_usuario(
    usuario_id: int, 
    nuevo_correo: str = Body(..., embed=True), 
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.correoElectronico = nuevo_correo
    db.commit()
    db.refresh(usuario)
    return usuario
@app.post("/usuarios/{usuario_id}/actualizar_contraseña")
def actualizar_contraseña(usuario_id: int, datos: ActualizarContraseña, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")


    if not pwd_context.verify(datos.contraseñaActual, usuario.contraseñaUsuario):
        raise HTTPException(status_code=400, detail="La contraseña actual es incorrecta")


    usuario.contraseñaUsuario = pwd_context.hash(datos.nuevaContraseña)
    db.commit()


    return {"message": "Contraseña actualizada exitosamente"}

@app.put("/usuarios/{user_id}/actualizar-foto")
async def actualizar_imagen(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # Añade esta dependencia
):
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    formatos_permitidos = ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/svg+xml", "image/webp"]
    if file.content_type not in formatos_permitidos:
        raise HTTPException(status_code=400, detail="Formato de archivo no soportado")
    
    directorio_imagenes = "Imagenes"
    os.makedirs(directorio_imagenes, exist_ok=True)
    file_location = os.path.join(directorio_imagenes, file.filename)
    with open(file_location, "wb") as buffer:
        buffer.write(await file.read())
    
    usuario.imagen = file_location
    db.commit()
    db.refresh(usuario)

    # Generar nuevo token con la imagen actualizada
    nuevo_token = crear_token_jwt(usuario)
    
    return {
        "message": "Foto de perfil actualizada exitosamente",
        "ruta": file_location,
        "token": nuevo_token  # Añade el nuevo token a la respuesta
    }

#-----------------------------------------------------------------------------------------
#Metodos de reserva

from datetime import datetime

# Método para obtener TODAS las reservas (sin filtrar por usuario)
@app.get("/reservas/", response_model=List[usu])
async def obtener_todas_reservas(db: Session = Depends(get_db)):
    reservas = db.query(Reserva).all()
    if not reservas:
        raise HTTPException(
            status_code=404,
            detail="No hay reservas registradas en el sistema"
        )
    return reservas

@app.post("/reservas/", response_model=usu)
async def crear_reserva(reserva: usu, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter(Plan.id == reserva.plan_id).first()
    
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="El plan seleccionado no existe"
        )
    
    if not plan.disponible:
        raise HTTPException(
            status_code=404,
            detail="El plan seleccionado no está disponible"
        )
    
    # 🔥 Verificar si el usuario ya tiene una reserva activa
    reserva_activa = db.query(Reserva).filter(
        Reserva.usuario_id == reserva.usuario_id,  # Asumo que reservas tienen el campo usuario_id
        #Reserva.estado == "activa",  # Asegúrate de que manejas un campo 'estado' (activa, cancelada, etc.)
        Reserva.fecha >= datetime.now()  # Solo importa si la fecha de la reserva es futura
    ).first()

    if reserva_activa:
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una reserva activa. Cancélala o espera a que termine para hacer otra."
        )

    # 🔹 Crear nueva reserva
    nueva_reserva = Reserva(**reserva.dict())
    nueva_reserva.estado = "activa"  # Marcar como activa al crearla
    db.add(nueva_reserva)
    db.commit()
    
    plan.cantidad_actual += 1
    if plan.cantidad_actual >= plan.cantidad_maxima:
        plan.disponible = False
    db.commit()
    
    db.refresh(nueva_reserva)
    return nueva_reserva


#Metodo de obtencionde todas las reservas de un usuario en especifico
@app.get("/reservas/{reserva_id}", response_model=usu)
async def obtener_reserva(reserva_id: int, db: Session = Depends(get_db)):
    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    if reserva is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    return reserva

#Metodo de actualizacion de reservas por usuario
@app.put("/reservas/{reserva_id}", response_model=usu)
async def actualizar_reserva(reserva_id: int, reserva_actualizada: usu, db: Session = Depends(get_db)):
    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    if reserva is None:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    
    for key, value in reserva_actualizada.dict().items():
        setattr(reserva, key, value)

    db.commit()
    db.refresh(reserva)
    return reserva

#Metodo de Eliminacion de reserva por id seleccionada
@app.delete("/reservas/{reserva_id}", status_code=200)
async def eliminar_reserva(reserva_id: int, db: Session = Depends(get_db)):
    reserva = db.query(Reserva).filter(Reserva.id == reserva_id).first()
    
    if not reserva:
        raise HTTPException(
            status_code=404,
            detail="Reserva no encontrada"
        )

    plan = db.query(Plan).filter(Plan.id == reserva.plan_id).first()
    
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Plan no encontrado"
        )

    db.delete(reserva)
    db.commit()

    plan.cantidad_actual -= 1

    if plan.cantidad_actual < plan.cantidad_maxima:
        plan.disponible = True
    
    db.commit()

    return {"detail": "Reserva eliminada con éxito"}

@app.post("/reservas/{id}/pagar")
async def pagar_reserva(id: int, db: Session = Depends(get_db)):

    reserva = db.query(Reserva).filter(Reserva.id == id).first()
    
    if not reserva:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")

    if reserva.pagada:
        raise HTTPException(status_code=400, detail="La reserva ya está pagada")
    

    reserva.pagada = True
    db.commit() 
    db.refresh(reserva)  
    
    return {"id": reserva.id, "usuario_id": reserva.usuario_id, "fecha": reserva.fecha, "pagada": reserva.pagada}

@app.get("/reservas/{usuario_id}/user")
async def obtener_reservas(usuario_id: int, db: Session = Depends(get_db)):
    reservas = db.query(Reserva).filter(Reserva.usuario_id == usuario_id).all()
    if not reservas:
        raise HTTPException(status_code=404, detail="No hay reservas para este usuario")
    return reservas


@app.delete("/reservas/eliminar_pasadas")
async def eliminar_reservas_pasadas(db: Session = Depends(get_db)):
    fecha_actual = date.today()
    
    reservas_pasadas = db.query(Reserva).filter(Reserva.fecha < fecha_actual).all()
    
    if not reservas_pasadas:
        raise HTTPException(
            status_code=404, 
            detail="No hay reservas pasadas para eliminar"
        )
    
    for reserva in reservas_pasadas:
        db.delete(reserva)
    
    db.commit()
    
    return {"message": f"Se eliminaron {len(reservas_pasadas)} reservas pasadas exitosamente"}

#-----------------------------------------------------------------------------------------
#Metodos de PQRS

@app.post("/pqr/", response_model=PQRS)
async def crear_pqr(pqr: PQRS, db: Session = Depends(get_db)):
    nuevo_pqr = Pqr(**pqr.dict())
    db.add(nuevo_pqr)
    db.commit()
    db.refresh(nuevo_pqr)
    return nuevo_pqr

@app.get("/pqrs/", response_model=List[PQRS])  
async def obtener_pqrs(db: Session = Depends(get_db)):
    pqrs = db.query(Pqr).all() 
    return pqrs

@app.get("/pqrs/{pqr_id}", response_model=PQRS)
async def obtener_pqr(pqr_id: int, db: Session = Depends(get_db)):
    pqr = db.query(Pqr).filter(Pqr.id == pqr_id).first()  
    if pqr is None:
        raise HTTPException(status_code=404, detail="PQR no encontrado")
    return pqr

@app.put("/pqrs/{pqr_id}", response_model=PQRS)
async def actualizar_pqr(pqr_id: int, pqr_actualizado: PQRS, db: Session = Depends(get_db)):
    pqr = db.query(Pqr).filter(Pqr.id == pqr_id).first() 
    if pqr is None:
        raise HTTPException(status_code=404, detail="PQR no encontrado")
    
    for key, value in pqr_actualizado.dict().items():
        setattr(pqr, key, value)

    db.commit()
    db.refresh(pqr)
    return pqr

@app.delete("/pqrs/{pqr_id}", response_model=PQRS)
async def eliminar_pqr(pqr_id: int, db: Session = Depends(get_db)):
    pqr = db.query(Pqr).filter(Pqr.id == pqr_id).first() 
    if pqr is None:
        raise HTTPException(status_code=404, detail="PQR no encontrado")
    
    db.delete(pqr)
    db.commit()
    return pqr

@app.put("/pqrs/{pqr_id}/respuesta", response_model=PQRS)
async def responder_pqr(pqr_id: int, respuesta_pqr: RespuestaPQR, db: Session = Depends(get_db)):
    pqr = db.query(Pqr).filter(Pqr.id == pqr_id).first()
    if not pqr:
        raise HTTPException(status_code=404, detail="PQR no encontrado")
    
    pqr.respuesta = respuesta_pqr.respuesta
    db.commit()
    db.refresh(pqr)
    return pqr


#-----------------------------------------------------------------------------------------
#Metodos de seguridad

#Metodo de Recuperacion de contraseña envio de el correo
@app.post("/recuperarpassword")
async def recuperar_password(request: EmailSchema, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correoElectronico == request.email).first()

    if not usuario:
        return {"mensaje": "Si el correo está registrado, recibirás un enlace de recuperación."}
    
    token = generar_token_reset(usuario.id, usuario.correoElectronico)
    
    await send_reset_email(usuario.correoElectronico, token)

    return {"mensaje": "Correo de recuperación enviado."}

#Metodo de recuperacion de contraseña Cambio de la contraseña y actualizacion de la contraseña 
@app.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    logger.debug(f"Datos recibidos: {request.dict()}")

    try:
        payload = verificar_token(request.token)
        email = payload.get("sub")
        user_id = payload.get("user_id")

        usuario = db.query(Usuario).filter(Usuario.id == user_id, Usuario.correoElectronico == email).first()
        if not usuario:
            raise HTTPException(status_code=400, detail="Usuario no encontrado.")

        usuario.contraseñaUsuario = pwd_context.hash(request.nueva_contraseña)
        db.commit()

        return {"mensaje": "Contraseña restablecida correctamente."}
    except jwt.JWTError:
        raise HTTPException(status_code=400, detail="Token inválido o expirado.")

#metodo para generar el token de recuperacion de contraseña
@app.post("/token", response_model=dict)
async def generar_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correoElectronico == form_data.username).first()
    if not usuario or not pwd_context.verify(form_data.password, usuario.contraseñaUsuario):
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = crear_token_jwt(data={"sub": str(usuario.id)}, expires_delta=access_token_expires)

    return {"access_token": access_token, "token_type": "bearer"}

#-----------------------------------------------------------------------------------------
#Metodos de Palnes

@app.put("/planes/{plan_id}", response_model=PlanResponse)
async def actualizar_plan(
    plan_id: int, 
    plan_actualizado: PlanCreate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verificar si el usuario es admin
    if not current_user.esAdmin:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar planes"
        )
    
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Verificar si el nuevo nombre ya existe en otro plan
    if plan_actualizado.nombre != plan.nombre:
        plan_existente = db.query(Plan).filter(
            Plan.nombre == plan_actualizado.nombre,
            Plan.id != plan_id
        ).first()
        if plan_existente:
            raise HTTPException(
                status_code=400,
                detail="Ya existe un plan con ese nombre"
            )

    # Actualizar los campos del plan
    plan.nombre = plan_actualizado.nombre
    plan.descripcion = plan_actualizado.descripcion
    plan.tipo = plan_actualizado.tipo
    plan.cantidad_maxima = plan_actualizado.cantidad_maxima
    plan.precio = plan_actualizado.precio
    
    # Actualizar disponibilidad basada en la nueva cantidad máxima
    if plan.cantidad_actual >= plan_actualizado.cantidad_maxima:
        plan.disponible = False
    else:
        plan.disponible = True

    db.commit()
    db.refresh(plan)
    return plan


@app.post("/planes/{plan_id}/imagen")
async def subir_imagen_plan(
    plan_id: int,
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verificar si el usuario es admin
    if not current_user.esAdmin:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar imágenes de planes"
        )
    
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Validar formato de imagen
    formatos_permitidos = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if imagen.content_type not in formatos_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagen no soportado"
        )

    # Crear directorio si no existe
    directorio_imagenes = "Imagenes/planes"
    os.makedirs(directorio_imagenes, exist_ok=True)
    
    # Generar nombre único para la imagen
    extension = os.path.splitext(imagen.filename)[1]
    nombre_imagen = f"plan_{plan_id}{extension}"
    file_location = os.path.join(directorio_imagenes, nombre_imagen)

    # Guardar la imagen
    with open(file_location, "wb") as buffer:
        buffer.write(await imagen.read())

    # Actualizar la ruta de la imagen en la base de datos
    plan.imagen = file_location
    db.commit()
    db.refresh(plan)

    return {
        "message": "Imagen del plan actualizada exitosamente",
        "ruta": file_location
    }

@app.get("/planes/{tipo}/tipo", response_model=List[PlanResponse])
def obtener_planes_por_tipo(
    tipo: str, 
    db: Session = Depends(get_db),
    disponibilidad: Optional[bool] = None
):
    try:
        # Validar que el tipo sea uno de los permitidos
        tipo_validado = TipoPlan(tipo)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de plan no válido. Los tipos permitidos son: {[e.value for e in TipoPlan]}"
        )
    
    query = db.query(Plan).filter(Plan.tipo == tipo_validado)
    
    # Filtrar por disponibilidad si se especifica
    if disponibilidad is not None:
        query = query.filter(Plan.disponible == disponibilidad)
    
    planes = query.all()
    
    if not planes:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontraron planes del tipo {tipo}"
        )
    
    return planes

@app.post("/planes", response_model=PlanResponse)
def crear_plan(
    plan: PlanCreate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verificar si el usuario es admin
    if not current_user.esAdmin:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para crear planes"
        )
    
    plan_existente = db.query(Plan).filter(Plan.nombre == plan.nombre).first()
    if plan_existente:
        raise HTTPException(
            status_code=400,
            detail="El nombre del plan ya existe"
        )
    
    nuevo_plan = Plan(
        nombre=plan.nombre,
        descripcion=plan.descripcion,
        tipo=plan.tipo,
        cantidad_maxima=plan.cantidad_maxima,
        cantidad_actual=0,
        disponible=True,
        precio=plan.precio,
        imagen=plan.imagen
    )
    
    db.add(nuevo_plan)
    db.commit()
    db.refresh(nuevo_plan)
    return nuevo_plan

@app.get("/planes/", response_model=List[PlanResponse])
async def obtener_planes(
    db: Session = Depends(get_db),
    disponibilidad: Optional[bool] = None,
    tipo: Optional[str] = None
):
    query = db.query(Plan)
    
    # Aplicar filtros si se proporcionan
    if disponibilidad is not None:
        query = query.filter(Plan.disponible == disponibilidad)
    
    if tipo is not None:
        try:
            tipo_validado = TipoPlan(tipo)
            query = query.filter(Plan.tipo == tipo_validado)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de plan no válido. Los tipos permitidos son: {[e.value for e in TipoPlan]}"
            )
    
    planes = query.all()
    return planes

@app.put("/planes/{plan_id}/actualizar-disponibilidad", response_model=PlanResponse)
def actualizar_disponibilidad(
    plan_id: int, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verificar si el usuario es admin
    if not current_user.esAdmin:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para actualizar disponibilidad de planes"
        )
    
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    # Actualizar disponibilidad basada en la capacidad
    if plan.cantidad_actual >= plan.cantidad_maxima:
        plan.disponible = False
    else:
        plan.disponible = True
    
    db.commit()
    db.refresh(plan)
    
    return plan


@app.delete("/planes/{plan_id}")
async def eliminar_plan(
    plan_id: int, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Verificar si el usuario es admin
    if not current_user.esAdmin:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para eliminar planes"
        )
    
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    
    reservas_asociadas = db.query(Reserva).filter(Reserva.plan_id == plan_id).first()
    if reservas_asociadas:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar el plan porque tiene reservas asociadas"
        )

    # Eliminar la imagen asociada si existe
    if plan.imagen and os.path.exists(plan.imagen):
        try:
            os.remove(plan.imagen)
        except Exception as e:
            logger.error(f"Error al eliminar la imagen del plan: {str(e)}")

    db.delete(plan)
    db.commit()

    return {"detail": "Plan eliminado exitosamente"}



@app.get("/planes/{plan_id}", response_model=PlanResponse)
async def obtener_plan(
    plan_id: int, 
    db: Session = Depends(get_db)
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return plan
#----------------------------------------------------------------------------------------------