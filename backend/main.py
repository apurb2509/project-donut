from fastapi import FastAPI

app = FastAPI(title="Project Donut API", version="0.1.0")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Project Donut FastAPI server is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
