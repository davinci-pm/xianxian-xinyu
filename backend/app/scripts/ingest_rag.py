import json
from dataclasses import asdict

from app.db.session import SessionLocal
from app.services.rag_ingest import ingest_fengge_corpus, ingest_vendored_persona_corpora


def main() -> None:
    with SessionLocal() as db:
        fengge_report = ingest_fengge_corpus(db)
        upstream_report = ingest_vendored_persona_corpora(db)
    print(
        json.dumps(
            {
                "fengge": asdict(fengge_report),
                "upstream_personas": asdict(upstream_report),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
