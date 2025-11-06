from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
	return {"status": "ok", "message": "Servidor en marcha"}


@app.get("/healthz")
def healthz():
	return {"status": "healthy"}
