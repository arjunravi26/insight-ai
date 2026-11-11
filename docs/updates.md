* User Login and Authenication and Authorization(JWT)
* Database(sqlite)
* Ownership - pdf, vector db
* Partial pinecone writes(exception trigger cases)
* Retry and Idempotency handling
* Unbounded ingestion pressure
* Make file writing asynchronous(aiofiles)
* Partial write of pdf - clean at startups
* Use 202(accepted) in ingestion scenario and fetch result later, same for generation
* Use async wherever possible
* Implement queue with proper backpressure
* Understand resource constraints and design system or accept request accordingly
* Semantic cache - for chunks and answer
* Cross encoder
* Observability and monitoring
* Data Retention policy - How many days should we keep these pdf
* Add proper sources with answer - (LLM output) using llm or manually
