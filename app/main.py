from fastapi import FastAPI

app = FastAPI(title="Vibecoding Bot")


@app.get("/health")
def healthcheck():
    return {"status": "ok"}
