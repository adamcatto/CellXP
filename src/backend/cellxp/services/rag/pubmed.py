"""NCBI PubMed and PubMed Central retrieval adapters."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import httpx

from .schemas import RetrievedChunk, RetrievedDocument, SearchHit, SearchRequest, SearchResult

_NCBI_EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class NcbiLiteratureClient:
    """Small synchronous NCBI E-utilities client with injectable HTTP transport.

    ``http_client`` owns connection policy and may include NCBI API-key parameters, retry logic,
    or a deterministic ``MockTransport`` in tests. The client never retries implicitly.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = _NCBI_EUTILS_URL,
    ) -> None:
        self._client = http_client or httpx.Client(timeout=20.0)
        self._base_url = base_url.rstrip("/")

    def search_pubmed(self, request: SearchRequest) -> SearchResult:
        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": request.query,
            "retmax": request.limit,
            "retmode": "json",
            "sort": "relevance",
        }
        if request.published_after:
            params.update(
                {"mindate": request.published_after, "maxdate": "3000", "datetype": "pdat"}
            )
        response = self._client.get(f"{self._base_url}/esearch.fcgi", params=params)
        response.raise_for_status()
        identifiers = response.json().get("esearchresult", {}).get("idlist", [])
        if not identifiers:
            return SearchResult(query=request.query)
        documents = self._fetch_pubmed(identifiers)
        by_id = {document.source_id.removeprefix("PMID:"): document for document in documents}
        hits = [
            _document_to_hit(by_id[identifier], rank, len(identifiers))
            for rank, identifier in enumerate(identifiers)
            if identifier in by_id
        ]
        return SearchResult(query=request.query, hits=hits)

    def retrieve(self, source: str, identifier: str) -> RetrievedDocument | None:
        normalized_source = source.casefold().replace(" ", "")
        bare_id = identifier.split(":", 1)[-1]
        if normalized_source in {"pubmed", "pmid"}:
            documents = self._fetch_pubmed([bare_id])
        elif normalized_source in {"pmc", "pubmedcentral"}:
            documents = self._fetch_pmc([bare_id.removeprefix("PMC")])
        else:
            raise ValueError(f"unsupported NCBI literature source: {source}")
        return documents[0] if documents else None

    def _fetch_pubmed(self, identifiers: Iterable[str]) -> list[RetrievedDocument]:
        response = self._client.get(
            f"{self._base_url}/efetch.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(identifiers),
                "rettype": "abstract",
                "retmode": "xml",
            },
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return [_parse_pubmed_article(article) for article in root.findall(".//PubmedArticle")]

    def _fetch_pmc(self, identifiers: Iterable[str]) -> list[RetrievedDocument]:
        response = self._client.get(
            f"{self._base_url}/efetch.fcgi",
            params={"db": "pmc", "id": ",".join(identifiers), "retmode": "xml"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        return [_parse_pmc_article(article) for article in root.findall(".//article")]


def _parse_pubmed_article(article: ET.Element) -> RetrievedDocument:
    pmid = _required_text(article, ".//MedlineCitation/PMID")
    title = _element_text(article.find(".//ArticleTitle")) or f"PubMed record {pmid}"
    abstract_parts = [
        text for element in article.findall(".//Abstract/AbstractText") if (text := _element_text(element))
    ]
    publication_date = _publication_date(article.find(".//PubDate"))
    doi = next(
        (
            _element_text(item)
            for item in article.findall(".//ArticleId")
            if item.attrib.get("IdType") == "doi"
        ),
        None,
    )
    citation = f"doi:{doi}" if doi else f"PMID:{pmid}"
    chunks = _text_chunks(
        "\n\n".join(abstract_parts),
        source_id=f"PMID:{pmid}",
        source_release=publication_date or "unknown",
    )
    return RetrievedDocument(
        source="PubMed",
        source_type="literature",
        source_id=f"PMID:{pmid}",
        title=title,
        citation=citation,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        publication_date=publication_date,
        chunks=chunks,
    )


def _parse_pmc_article(article: ET.Element) -> RetrievedDocument:
    pmc_id = next(
        (
            _element_text(item)
            for item in article.findall(".//article-id")
            if item.attrib.get("pub-id-type") == "pmc"
        ),
        None,
    )
    if not pmc_id:
        raise ValueError("PMC response is missing a pmc article-id")
    pmc_id = pmc_id if pmc_id.startswith("PMC") else f"PMC{pmc_id}"
    doi = next(
        (
            _element_text(item)
            for item in article.findall(".//article-id")
            if item.attrib.get("pub-id-type") == "doi"
        ),
        None,
    )
    title = _element_text(article.find(".//article-title")) or f"PMC record {pmc_id}"
    publication_date = _publication_date(article.find(".//pub-date"))
    body = "\n\n".join(
        text
        for element in article.findall(".//abstract") + article.findall(".//body/sec")
        if (text := _element_text(element))
    )
    return RetrievedDocument(
        source="PMC",
        source_type="literature",
        source_id=pmc_id,
        title=title,
        citation=f"doi:{doi}" if doi else pmc_id,
        url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmc_id}/",
        publication_date=publication_date,
        chunks=_text_chunks(
            body, source_id=pmc_id, source_release=publication_date or "unknown"
        ),
    )


def _document_to_hit(document: RetrievedDocument, rank: int, total: int) -> SearchHit:
    snippet = document.chunks[0].text if document.chunks else None
    return SearchHit(
        source=document.source,
        source_type=document.source_type,
        source_id=document.source_id,
        title=document.title,
        citation=document.citation,
        url=document.url,
        publication_date=document.publication_date,
        source_release=document.publication_date,
        rank_score=max(0.0, 1.0 - rank / max(total, 1)),
        snippet=snippet,
    )


def _text_chunks(
    text: str, *, source_id: str, source_release: str, max_characters: int = 2_000
) -> list[RetrievedChunk]:
    passages = [text[index : index + max_characters] for index in range(0, len(text), max_characters)]
    return [
        RetrievedChunk(
            chunk_id=_sha256(f"{source_id}:{index}:{passage}"),
            text=passage,
            chunk_hash=f"sha256:{_sha256(passage)}",
            source_id=source_id,
            source_release=source_release,
            embedding_model="not-indexed",
        )
        for index, passage in enumerate(passages)
        if passage.strip()
    ]


def _publication_date(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    year = _first_text(element, "year", "Year")
    month = _first_text(element, "month", "Month")
    day = _first_text(element, "day", "Day")
    if not year:
        return _first_text(element, "medlineDate", "MedlineDate")
    return "-".join(value for value in (year, month, day) if value)


def _first_text(element: ET.Element, *tags: str) -> str | None:
    for tag in tags:
        value = _element_text(element.find(tag))
        if value:
            return value
    return None


def _required_text(element: ET.Element, path: str) -> str:
    value = _element_text(element.find(path))
    if not value:
        raise ValueError(f"NCBI response is missing {path}")
    return value


def _element_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
