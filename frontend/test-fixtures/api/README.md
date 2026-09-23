# API contract fixture

`e0001-recommendations.json` is the unmodified synthetic HTTP example published by the team integration branch, pinned to commit `3a90322a728f592888929903cb4a9f671d048b3e`:

https://github.com/BAITC-Hacks/hack-7b100a71-garden/blob/3a90322a728f592888929903cb4a9f671d048b3e/docs/e0001-recommendations.response.json

It is used only by adapter tests. Production components and the mock adapter do not import it. The corresponding mapping contract is `docs/FRONTEND_API_CONTRACT.md` at that commit. The example was produced by the backend's FastAPI TestClient against the official synthetic dataset, with deterministic explanations; it is not evidence of a running endpoint in this checkout.
