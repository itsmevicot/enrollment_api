# Age Groups API

This is a simple CRUD microservice for managing age groups.

## Overview

- Built with FastAPI and MongoDB (with `mongomock` for tests).
- Dependency injection via FastAPI `Depends` pattern.
- Comprehensive pytest suite with automatic collection cleanup.

## Prerequisites

- Python 3.10+
- [Docker](https://www.docker.com/) & [Docker Compose](https://docs.docker.com/compose/) (optional, for containerized deployment)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/itsmevicot/age_groups_api.git
   cd age_groups_api
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate       # Windows
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Configuration

Copy the sample environment file and adjust values if needed:
```bash
cp .env .env.example
```

## Running the API

### 1. Without Docker

```bash
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --reload
```

- The `--reload` flag enables hot-reload on code changes.
- Open your browser to `http://localhost:8000/docs` for the interactive Swagger UI.

### 2. With Docker Compose

Start MongoDB and the API:
```bash
docker-compose up -d
```

Follow the API logs:
```bash
docker-compose logs -f api
```

Stop everything:
```bash
docker-compose down
```

## API Endpoints

| Method | Path                 | Description                       |
| ------ | -------------------- | --------------------------------- |
| POST   | `/age-groups/`       | Create a new age group            |
| GET    | `/age-groups/`       | List all age groups               |
| GET    | `/age-groups/{id}`   | Get a single age group by ID      |
| DELETE | `/age-groups/{id}`   | Delete an age group by ID         |

### Example cURL

```bash
# Create
curl -X POST http://localhost:8000/age-groups/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Kids","min_age":0,"max_age":12}'

# List
curl http://localhost:8000/age-groups/

# Get
curl http://localhost:8000/age-groups/{id}

# Delete
curl -X DELETE http://localhost:8000/age-groups/{id}
```

## Running Tests

Tests use `mongomock` under the hood—no real MongoDB is required.

```bash
# in your activated virtualenv or container
pytest
```

Or via Docker Compose:
```bash
docker-compose exec api pytest
```
