"""Network-free PubMed and PMC adapter tests (RAG-2, RAG-3)."""

from __future__ import annotations

import json

import httpx

from cellxp.services.rag.pubmed import NcbiLiteratureClient
from cellxp.services.rag.schemas import SearchRequest

PUBMED_XML = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation>
<PMID>123</PMID><Article><ArticleTitle>Variant evidence</ArticleTitle>
<Abstract><AbstractText Label="BACKGROUND">Direct supporting abstract.</AbstractText></Abstract>
<Journal><JournalIssue><PubDate><Year>2025</Year><Month>06</Month></PubDate></JournalIssue></Journal>
</Article></MedlineCitation><PubmedData><ArticleIdList>
<ArticleId IdType="doi">10.1000/example</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle></PubmedArticleSet>"""

PMC_XML = b"""<pmc-articleset><article><front><article-meta>
<article-id pub-id-type="pmc">456</article-id><article-id pub-id-type="doi">10.1000/pmc</article-id>
<title-group><article-title>Full text evidence</article-title></title-group>
<pub-date><year>2024</year><month>12</month><day>03</day></pub-date>
<abstract><p>Abstract passage.</p></abstract></article-meta></front>
<body><sec><title>Results</title><p>Full text result.</p></sec></body></article></pmc-articleset>"""


def _transport(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("esearch.fcgi"):
        assert request.url.params["term"] == "TP53"
        return httpx.Response(
            200, content=json.dumps({"esearchresult": {"idlist": ["123"]}}).encode()
        )
    if request.url.params.get("db") == "pubmed":
        return httpx.Response(200, content=PUBMED_XML)
    if request.url.params.get("db") == "pmc":
        return httpx.Response(200, content=PMC_XML)
    return httpx.Response(404)


def _client() -> NcbiLiteratureClient:
    return NcbiLiteratureClient(
        http_client=httpx.Client(transport=httpx.MockTransport(_transport))
    )


def test_pubmed_search_resolves_metadata_and_abstract() -> None:
    result = _client().search_pubmed(SearchRequest(query=" TP53 ", limit=3))

    assert result.query == "TP53"
    assert result.hits[0].source_id == "PMID:123"
    assert result.hits[0].citation == "doi:10.1000/example"
    assert result.hits[0].snippet == "Direct supporting abstract."
    assert result.hits[0].publication_date == "2025-06"


def test_pubmed_retrieve_has_stable_chunk_provenance() -> None:
    document = _client().retrieve("PubMed", "PMID:123")

    assert document is not None
    assert document.url == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert document.chunks[0].source_release == "2025-06"
    assert document.chunks[0].chunk_hash.startswith("sha256:")


def test_pmc_retrieve_parses_full_text_and_resolvable_url() -> None:
    document = _client().retrieve("PMC", "PMC456")

    assert document is not None
    assert document.source_id == "PMC456"
    assert document.citation == "doi:10.1000/pmc"
    assert "Full text result." in document.chunks[0].text
    assert document.url == "https://pmc.ncbi.nlm.nih.gov/articles/PMC456/"


def test_empty_pubmed_search_is_valid() -> None:
    client = NcbiLiteratureClient(
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"esearchresult": {"idlist": []}}
                )
            )
        )
    )
    assert client.search_pubmed(SearchRequest(query="no hits")).hits == []
