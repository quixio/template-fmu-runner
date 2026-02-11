@echo off
REM Stop local development environment (Windows)

cd /d "%~dp0.."

echo Stopping local development environment...
docker-compose -f docker-compose.local.yml down

echo Done.
