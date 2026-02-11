@echo off
REM Start local development environment (Windows)

cd /d "%~dp0.."

if not exist .env (
    echo Error: .env file not found. Copy .env.example to .env and add your secrets.
    exit /b 1
)

echo Starting local development environment...
docker-compose -f docker-compose.local.yml up -d

echo.
echo Services starting:
echo   - Frontend:  http://localhost:3000
echo   - API:       http://localhost:8080
echo   - MinIO:     http://localhost:9001
echo.
echo Use 'docker-compose -f docker-compose.local.yml logs -f' to view logs
