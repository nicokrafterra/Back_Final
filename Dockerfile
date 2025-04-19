#Imagen para trabajar con fastapi
FROM bitnami/python:3.13.2

#Para guardar la carpeta en el container
WORKDIR /app

#Para guardar las dependencias

COPY requirements.txt .

#...
RUN pip install --no-cache-dir -r requirements.txt

#Para pasar todas las carpetas del proyecto
COPY . .

#Para Iniciar el puerto 8888
EXPOSE 8888

#...
CMD [ "uvicorn", "vista:app", "--host", "0.0.0.0", "--port", "8000", "--reload" ]