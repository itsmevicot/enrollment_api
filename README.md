# Enrollment API  

This is the **Enrollment API**, a FastAPI service for handling enrollment requests.  
It works in tandem with the [Age Groups API](https://github.com/itsmevicot/age_groups_api), which provides the valid age ranges for acceptance.  
The Enrollment API writes new requests to MongoDB, publishes them to RabbitMQ, and processes them via a standalone worker.  

---

## Architecture Overview

```mermaid
flowchart LR
  Client -->|POST /enrollments| EnrollmentAPI[FastAPI Enrollment API]
  EnrollmentAPI --> Mongo[(MongoDB)]
  EnrollmentAPI --> Rabbit[(RabbitMQ)]
  Rabbit --> Worker[Enrollment Worker]
  Worker --> Mongo[(MongoDB)]
  Worker -->|HTTP| AgeAPI[Age Groups API]
```

1. **API** writes the enrollment document to MongoDB with `status = pending`, then publishes the new ID to RabbitMQ.  
2. **Worker** (standalone script) consumes the queue, calls the EnrollmentAPI over HTTP, and updates the document in MongoDB to `approved`, `rejected`, or `failed`, recording timestamps.  

---

## Getting Started  

### Prerequisites  

- Docker & Docker Compose  
- `.env` file in project root with the following variables:
  ```dotenv
  ENVIRONMENT=development
  PORT=8001
  MONGO_URI=mongodb://mongo:27017/age_groups_db
  MONGO_DB_NAME=age_groups_db
  RABBIT_URI=amqp://guest:guest@rabbitmq:5672/
  RABBIT_QUEUE_NAME=enrollments
  AGE_GROUPS_API_URL=http://age-groups-api:8000
  ```

### Running Locally with Docker Compose  

```bash
# build and start all services
docker-compose up --build
```

This brings up:

- **enrollment-api** on `http://localhost:${PORT}`  
- **rabbitmq** management UI on `http://localhost:15672` (guest/guest)  
- **processor** worker consuming enrollment messages  


### API Endpoints  

| Method | Path                | Description                           |
|--------|---------------------|---------------------------------------|
| GET    | `/health`           | Health check (Mongo & Rabbit)         |
| POST   | `/enrollments/`     | Create new enrollment (pending)       |
| GET    | `/enrollments/`     | List all enrollments                  |
| GET    | `/enrollments/{id}` | Fetch a single enrollment by ID       |
| DELETE | `/enrollments/{id}` | Delete an enrollment                  |

### Testing  

Run integrated tests with Pytest:

```bash
# inside the api container
docker-compose exec enrollment-api pytest
# or on host:
pytest
```

All business rules are covered by tests in `app/tests/test_enrollment.py`.

---

## Business Rules Summary  

1. **CPF Validation & Normalization**  
   - CPF strings are stripped to digits only and validated. Invalid CPFs return HTTP 422.

2. **No Duplicate Pending/Approved**  
   - A CPF with an existing **pending** or **approved** enrollment cannot register again (HTTP 400).

3. **Rejection Limit**  
   - More than 3 prior **rejected** enrollments for the same CPF blocks new requests (HTTP 400).

4. **Age Group Check**  
   - Worker queries the Age Groups API; if the applicant’s age is not within any defined bucket, they are **rejected** with a reason.

5. **Approval Logic**  
   - If no conflicts and age is valid, status is updated to **approved**.

6. **Failure Handling**  
   - If Age Groups API is unreachable after retries, enrollment status becomes **failed**.

7. **Timestamps**  
   - Each enrollment records `created_at` (UTC, timezone-aware) and `processed_at` (UTC) once the worker completes processing.

8. **Durable Messaging & Retries**  
   - RabbitMQ queue is declared with a dead-letter exchange and message TTL, so un-acked messages automatically retry every 5 minutes.

---

