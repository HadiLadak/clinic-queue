from fastapi import FastAPI

app = FastAPI(title="Clinic Queue")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: the process is up and serving requests."""
    return {"status": "ok"}
