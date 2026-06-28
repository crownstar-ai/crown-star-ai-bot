from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.license_middleware import LicenseMiddleware
from api.health import router as health_router

app = FastAPI(title="CrownStar API", version="7.0.1")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# License middleware (enforces tier)
app.add_middleware(LicenseMiddleware)

# Include health router
app.include_router(health_router, prefix="/v1")

@app.get("/")
async def root():
    return {"message": "CrownStar API", "version": "7.0.1"}
