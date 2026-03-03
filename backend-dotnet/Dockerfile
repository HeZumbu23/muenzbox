# ── Stage 1: Build the .NET application ───────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

COPY MuenzboxApi/MuenzboxApi.csproj MuenzboxApi/
RUN dotnet restore MuenzboxApi/MuenzboxApi.csproj

COPY MuenzboxApi/ MuenzboxApi/
RUN dotnet publish MuenzboxApi/MuenzboxApi.csproj \
    -c Release -o /app/publish \
    --no-restore

# ── Stage 2: ASP.NET Core 9 runtime (includes Microsoft.AspNetCore.App) ────
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS dotnet-runtime

# ── Stage 3: Python 3.12 base + .NET 9 runtime + Python packages ──────────
# python:3.12 is Debian Bookworm; compiled with --enable-shared so
# libpython3.12.so.1.0 is available for Python.NET.
FROM python:3.12 AS final

# Copy .NET runtime directly from the official image (no apt/wget needed)
COPY --from=dotnet-runtime /usr/share/dotnet /usr/share/dotnet
RUN ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

# Install Python packages required by the Nintendo bridge
RUN pip install --no-cache-dir pynintendoparental aiohttp

WORKDIR /app
COPY --from=build /app/publish .

# Point Python.NET to the CPython shared library.
# python:3.12 installs Python from source to /usr/local, so the .so is here:
ENV PYTHONNET_PYDLL=/usr/local/lib/libpython3.12.so.1.0

# Ensure Python can find the bridge module (handled in code, but set as fallback)
ENV PYTHONPATH=/app/Nintendo

# Database and runtime defaults (override via docker-compose environment)
ENV DATABASE_PATH=/data/muenzbox.db
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false

EXPOSE 8420

ENTRYPOINT ["dotnet", "MuenzboxApi.dll"]
