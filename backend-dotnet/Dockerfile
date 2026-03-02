# ── Stage 1: Build the .NET application ───────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

COPY MuenzboxApi/MuenzboxApi.csproj MuenzboxApi/
RUN dotnet restore MuenzboxApi/MuenzboxApi.csproj

COPY MuenzboxApi/ MuenzboxApi/
RUN dotnet publish MuenzboxApi/MuenzboxApi.csproj \
    -c Release -o /app/publish \
    --no-restore

# ── Stage 2: Python 3.12 base + .NET 9 runtime + Python packages ──────────
# python:3.12 is Debian Bookworm; compiled with --enable-shared so
# libpython3.12.so.1.0 is available for Python.NET.
FROM python:3.12 AS final

# Install .NET 9 runtime from Microsoft packages
RUN apt-get update && apt-get install -y --no-install-recommends wget && \
    wget -q https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
         -O /tmp/packages-microsoft-prod.deb && \
    dpkg -i /tmp/packages-microsoft-prod.deb && \
    rm /tmp/packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y --no-install-recommends dotnet-runtime-9.0 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

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
