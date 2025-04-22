from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from conexion import get_db
from sqlalchemy.exc import SQLAlchemyError
import os

app = FastAPI()

@app.post("/alter-planes")
async def alter_planes(db: Session = Depends(get_db)):
    if os.getenv("ENV") != "development":
        raise HTTPException(status_code=403, detail="Modificación de tablas solo permitida en desarrollo")

    try:
        # Agregar la columna imagen si no existe
        db.execute(text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS imagen VARCHAR(255)"))

        # Agregar la columna precio si no existe
        db.execute(text("ALTER TABLE planes ADD COLUMN IF NOT EXISTS precio INTEGER DEFAULT 0 NOT NULL"))

        db.commit()
        return {"message": "Tabla 'planes' actualizada correctamente"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
