"""
FastAPI application entry point for Clinical Trial Simulator.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from .config import get_settings, setup_directories
from .routes import get_routers
from .database import get_db
from .ml_service import get_ml_service
from .logging_config import setup_logging

# Configure logging (file + console)
setup_logging(log_level=logging.DEBUG)  # DEBUG level for detailed logs
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("="*78)
    logger.info("  Clinic-Buddy - Clinical Trial Simulator & Predictor")
    logger.info("  Developed with Cursor | Powered by Claude Sonnet 4.5 (AWS Bedrock)")
    logger.info("="*78)
    
    # Setup directories
    setup_directories()
    logger.info("Directories initialized")
    
    # Initialize database
    db = get_db()
    logger.info("Database initialized")
    
    # Initialize ML service
    ml_service = get_ml_service()
    
    # Log model configuration
    if ml_service.use_local_model:
        logger.info(f"AI Model: LOCAL MODEL (Device: {ml_service.device})")
        logger.info("Starting model download/loading (this may take a few minutes on first run)...")
        if ml_service.load_model():
            logger.info("✓ Model loaded successfully on startup")
        else:
            logger.warning("✗ Failed to load model on startup - will retry on first request")
    else:
        # Log AWS Bedrock API info
        model_info = ml_service.get_model_info()
        bedrock_ready = model_info.get('aws_bedrock_configured', False)
        logger.info(f"AI Model: AWS Bedrock - Claude Sonnet 4.5")
        logger.info(f"AWS Bedrock Status: {'✓ Connected' if bedrock_ready else '✗ Not Available'}")
    
    # Log Google Cloud Voice services
    logger.info("Voice Services: Google Cloud (Speech-to-Text & Text-to-Speech)")
    
    logger.info(f"Application started on http://{settings.APP_HOST}:{settings.APP_PORT}")
    logger.info("="*78)
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Cleanup ML service
    if ml_service.model_loaded:
        ml_service.unload_model()
        logger.info("ML model unloaded")
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered clinical trial simulation and prediction platform",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Setup templates
templates = Jinja2Templates(directory="templates")


# Include API routers
for router in get_routers():
    app.include_router(router)


# Authentication Routes
from .auth import get_auth
from fastapi import Form, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    login: str
    password: str
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None

class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    username: str
    email: str
    password: str

class ProfileUpdateRequest(BaseModel):
    first_name: str
    last_name: str
    email: str

class EmailVerifyRequest(BaseModel):
    email: str

class PasswordResetRequest(BaseModel):
    email: str
    new_password: str

@app.post("/api/auth/login")
async def login_api(request: LoginRequest, req: Request):
    """API endpoint for user login with GPS-based location tracking."""
    auth = get_auth()
    result = auth.authenticate_user(request.login, request.password)
    
    # Track location on successful login using GPS coordinates
    if result.get('success'):
        from .location_tracker import get_location_tracker
        tracker = get_location_tracker()
        
        user_data = result.get('user', {})
        user_id = str(user_data.get('index', 'unknown'))
        username = user_data.get('username', 'unknown')
        
        # Log location with GPS coordinates
        try:
            location_data = await tracker.log_login_gps(
                req, 
                user_id, 
                username,
                gps_latitude=request.gps_latitude,
                gps_longitude=request.gps_longitude,
                gps_accuracy=request.gps_accuracy
            )
            logger.info(f"✓ GPS location tracked for user {username}: {location_data.get('city', 'Unknown')}")
        except Exception as e:
            logger.error(f"Location tracking failed: {str(e)}")
            # Don't fail login if location tracking fails
    
    return JSONResponse(content=result)

@app.post("/api/auth/register")
async def register_api(request: RegisterRequest):
    """API endpoint for user registration."""
    auth = get_auth()
    result = auth.register_user(
        first_name=request.first_name,
        last_name=request.last_name,
        username=request.username,
        email=request.email,
        password=request.password
    )
    return JSONResponse(content=result)

@app.get("/api/auth/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    auth = get_auth()
    user = auth.verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return JSONResponse(content={"success": True, "user": user})

@app.put("/api/auth/profile")
async def update_profile(request: ProfileUpdateRequest, authorization: Optional[str] = Header(None)):
    """Update user profile."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.split(" ")[1]
    auth = get_auth()
    user = auth.verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = auth.update_user_profile(
        username=user['username'],
        first_name=request.first_name,
        last_name=request.last_name,
        email=request.email
    )
    
    return JSONResponse(content=result)

@app.post("/api/auth/verify-email")
async def verify_email(request: EmailVerifyRequest):
    """Verify email exists for password reset."""
    auth = get_auth()
    # Check if email exists
    import csv
    try:
        with open(auth.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['email'].lower() == request.email.lower():
                    return JSONResponse(content={"success": True, "message": "Email verified"})
        return JSONResponse(content={"success": False, "message": "Email not found"})
    except Exception as e:
        return JSONResponse(content={"success": False, "message": str(e)})

@app.post("/api/auth/reset-password")
async def reset_password(request: PasswordResetRequest):
    """Reset user password."""
    auth = get_auth()
    result = auth.reset_password(request.email, request.new_password)
    return JSONResponse(content=result)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    try:
        return templates.TemplateResponse("login.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering login page: {e}")
        return HTMLResponse(content="<h1>Login page - Template not found</h1>")

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    try:
        return templates.TemplateResponse("register.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering register page: {e}")
        return HTMLResponse(content="<h1>Register page - Template not found</h1>")

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """User profile page."""
    try:
        return templates.TemplateResponse("profile.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering profile page: {e}")
        return HTMLResponse(content="<h1>Profile page - Template not found</h1>")

@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password page."""
    try:
        return templates.TemplateResponse("forgot_password.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering forgot password page: {e}")
        return HTMLResponse(content="<h1>Forgot Password page - Template not found</h1>")

@app.get("/logout")
async def logout():
    """Logout redirect."""
    return RedirectResponse(url="/login")

@app.get("/simulations", response_class=HTMLResponse)
async def simulations_page(request: Request):
    """All simulations list page."""
    try:
        return templates.TemplateResponse("simulations.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering simulations page: {e}")
        return HTMLResponse(content="<h1>Simulations page - Template not found</h1>")

@app.get("/update-simulation", response_class=HTMLResponse)
async def update_simulation_page(request: Request, simulation_id: Optional[str] = None):
    """Update simulation page."""
    try:
        return templates.TemplateResponse("update_simulation.html", {
            "request": request,
            "simulation_id": simulation_id or ""
        })
    except Exception as e:
        logger.error(f"Error rendering update simulation page: {e}")
        return HTMLResponse(content="<h1>Update Simulation page - Template not found</h1>")

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat assistant page."""
    try:
        return templates.TemplateResponse("chat.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering chat page: {e}")
        return HTMLResponse(content="<h1>Chat page - Template not found</h1>")


@app.get("/docs", response_class=HTMLResponse)
async def api_documentation_page(request: Request):
    """Custom API documentation page."""
    try:
        return templates.TemplateResponse("api_docs.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering API docs page: {e}")
        return HTMLResponse(content="<h1>API Documentation - Template not found</h1>")


@app.get("/index", response_class=HTMLResponse)


# Web UI Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Landing page / dashboard."""
    try:
        db = get_db()
        stats = db.get_historical_stats()
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "app_name": settings.APP_NAME,
                "stats": stats
            }
        )
    except Exception as e:
        logger.error(f"Error rendering home page: {e}")
        # Fallback response
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{settings.APP_NAME}</title>
            <style>
                body {{
                    font-family: system-ui, -apple-system, sans-serif;
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }}
                .container {{
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    padding: 40px;
                    backdrop-filter: blur(10px);
                }}
                h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
                .subtitle {{ font-size: 1.2em; opacity: 0.9; margin-bottom: 30px; }}
                .features {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    margin-top: 30px;
                }}
                .feature {{
                    background: rgba(255,255,255,0.1);
                    padding: 20px;
                    border-radius: 10px;
                }}
                .cta {{
                    margin-top: 30px;
                    padding: 15px 30px;
                    background: white;
                    color: #667eea;
                    border: none;
                    border-radius: 10px;
                    font-size: 1.1em;
                    font-weight: bold;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                }}
                .cta:hover {{ transform: scale(1.05); }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🏥 Clinical Trial Predictor</h1>
                <div class="subtitle">AI-Powered Simulation & Analysis Platform</div>
                
                <p>Welcome to the Clinical Trial Simulator - your intelligent companion for predicting and optimizing clinical trial outcomes.</p>
                
                <div class="features">
                    <div class="feature">
                        <h3>🎯 Smart Simulation</h3>
                        <p>Run realistic trial simulations with AI-powered predictions</p>
                    </div>
                    <div class="feature">
                        <h3>🤖 AI Agents</h3>
                        <p>Research, predict, and optimize with specialized agents</p>
                    </div>
                    <div class="feature">
                        <h3>📊 Data Analytics</h3>
                        <p>Analyze historical trials and identify success patterns</p>
                    </div>
                    <div class="feature">
                        <h3>⚡ GPU Accelerated</h3>
                        <p>Fast predictions powered by advanced ML models</p>
                    </div>
                </div>
                
                <a href="/api/docs" class="cta">Explore API Documentation →</a>
            </div>
        </body>
        </html>
        """)


@app.get("/simulator", response_class=HTMLResponse)
async def simulator_page(request: Request):
    """Trial simulator interface."""
    try:
        return templates.TemplateResponse(
            "simulator.html",
            {
                "request": request,
                "app_name": settings.APP_NAME
            }
        )
    except Exception as e:
        logger.error(f"Error rendering simulator page: {e}")
        return HTMLResponse(content="<h1>Simulator page - Template not found</h1>")


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request, simulation_id: Optional[str] = None):
    """Results visualization page with query parameter."""
    try:
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "simulation_id": simulation_id or "",
                "app_name": settings.APP_NAME
            }
        )
    except Exception as e:
        logger.error(f"Error rendering results page: {e}")
        return HTMLResponse(content=f"<h1>Results for {simulation_id}</h1>")


@app.get("/results/{simulation_id}", response_class=HTMLResponse)
async def results_page_with_id(request: Request, simulation_id: str):
    """Results visualization page with path parameter."""
    try:
        logger.info(f"📊 Loading results page for simulation: {simulation_id}")
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "simulation_id": simulation_id,
                "app_name": settings.APP_NAME
            }
        )
    except Exception as e:
        logger.error(f"Error rendering results page for {simulation_id}: {e}")
        return HTMLResponse(content=f"<h1>Error loading results for {simulation_id}</h1>")


@app.get("/analyze-setup/{simulation_id}", response_class=HTMLResponse)
async def analyze_setup_page(request: Request, simulation_id: str):
    """Analyze clinical trial setup image page."""
    try:
        logger.info(f"🔬 Loading analyze setup page for simulation: {simulation_id}")
        return templates.TemplateResponse(
            "analyze_setup.html",
            {
                "request": request,
                "simulation_id": simulation_id,
                "app_name": settings.APP_NAME
            }
        )
    except Exception as e:
        logger.error(f"Error rendering analyze setup page for {simulation_id}: {e}")
        return HTMLResponse(content=f"<h1>Error loading analyze setup for {simulation_id}</h1>")


@app.get("/coming-soon", response_class=HTMLResponse)
async def coming_soon_page(request: Request):
    """Coming soon page for features under development."""
    try:
        return templates.TemplateResponse(
            "coming_soon.html",
            {
                "request": request,
                "app_name": settings.APP_NAME
            }
        )
    except Exception as e:
        logger.error(f"Error rendering coming soon page: {e}")
        return HTMLResponse(content="<h1>Feature Coming Soon</h1><p>Developer needs more time to prepare MVP</p>")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404 error handler."""
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>404 - Not Found</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .error-container {
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                }
                h1 { font-size: 4em; margin: 0; }
                p { font-size: 1.2em; }
                a { color: white; text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>404</h1>
                <p>Page not found</p>
                <a href="/">← Back to Home</a>
            </div>
        </body>
        </html>
        """,
        status_code=404
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """500 error handler."""
    logger.error(f"Internal server error: {exc}")
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>500 - Internal Server Error</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    color: white;
                }
                .error-container {
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 20px;
                    backdrop-filter: blur(10px);
                }
                h1 { font-size: 4em; margin: 0; }
                p { font-size: 1.2em; }
                a { color: white; text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>500</h1>
                <p>Internal server error</p>
                <a href="/">← Back to Home</a>
            </div>
        </body>
        </html>
        """,
        status_code=500
    )


# Development server
def main():
    """Run the application in development mode."""
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()
