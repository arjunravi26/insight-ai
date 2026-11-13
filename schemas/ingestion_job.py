from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngestionJobPayload:
    job_id: str
    document_id: str
    user_id: int
    file_path: str
    filename: str
    attempts: int
    max_attempts: int
    lock_token: str
