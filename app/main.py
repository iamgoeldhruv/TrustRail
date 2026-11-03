from fastapi import FastAPI

app = FastAPI(
    title="TrustRail",
    description="Authorization and transaction-control layer for AI agents",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "trustrail",
    }