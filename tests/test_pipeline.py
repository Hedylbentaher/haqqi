from haqqi.ingestion.pipeline import ingest, load_store


def _run(corpus_dir, **kw):
    return ingest(
        sources_file=corpus_dir / "sources.json",
        raw_dir=corpus_dir / "raw",
        articles_file=corpus_dir / "processed" / "articles.jsonl",
        manifest_file=corpus_dir / "processed" / "manifest.json",
        **kw,
    )


def _store(corpus_dir):
    return load_store(corpus_dir / "processed" / "articles.jsonl")


def test_first_ingestion_creates_records(corpus_dir):
    report = _run(corpus_dir)
    assert all(d.status == "ingested" for d in report.docs)
    store = _store(corpus_dir)
    rec = store["ct_fr/ct:6-4"]
    # métadonnées présentes
    for key in ("article_key", "lang", "version", "date", "section", "page", "text_norm", "hash"):
        assert key in rec
    assert rec["lang"] == "fr" and rec["article_key"] == "ct:6-4"
    # la loi de promulgation (articles 1-2) ET le code (articles 1-2) sont tous gardés
    assert {"ct_fr/ct@partie1:1", "ct_fr/ct:1", "ct_ar/ct@partie1:1", "ct_ar/ct:1"} <= store.keys()
    assert sum(r["doc_id"] == "ct_ar" for r in store.values()) == 6


def test_latest_version_is_current(corpus_dir):
    _run(corpus_dir)
    store = _store(corpus_dir)
    old_fr, new_fr = store["ct_fr/ct:6-4"], store["loi_fr/ct:6-4"]
    assert new_fr["is_current"] is True
    assert old_fr["is_current"] is False and old_fr["replaced_by"] == "loi_2025_9"
    # un article non modifié par la loi reste en vigueur
    assert store["ct_fr/ct:234bis"]["is_current"] is True
    # versions arabes gérées séparément des françaises
    assert store["loi_ar/ct:6-4"]["is_current"] is True
    assert store["ct_ar/ct:6-4"]["is_current"] is False


def test_second_run_skips_unchanged_files(corpus_dir):
    _run(corpus_dir)
    report = _run(corpus_dir)
    assert all(d.status == "unchanged" for d in report.docs)


def test_update_detects_modified_and_removed_articles(corpus_dir):
    _run(corpus_dir)
    path = corpus_dir / "raw" / "ct_fr.txt"
    text = path.read_text(encoding="utf-8")
    text = text.replace("Ancienne version d'exemple de l'article 30.", "Texte corrigé de l'article 30.")
    text = text.replace("Article 234 bis - Texte d'exemple de l'article 234 bis.\n", "")
    path.write_text(text, encoding="utf-8")

    report = _run(corpus_dir, only=["ct_fr"])
    doc = report.docs[0]
    assert (doc.updated, doc.removed) == (1, 1)
    store = _store(corpus_dir)
    assert "corrigé" in store["ct_fr/ct:30"]["text"]
    assert "ct_fr/ct:234bis" not in store


def test_missing_file_is_reported(corpus_dir):
    (corpus_dir / "raw" / "loi_ar.txt").unlink()
    report = _run(corpus_dir)
    statuses = {d.doc_id: d.status for d in report.docs}
    assert statuses["loi_ar"] == "missing"