from app.models import CollectedRecord
from app.services.source_loader import SourceCatalog


class ClassificationResult:
    def __init__(self, score: int, severity_bucket: str, reasons: list[str]) -> None:
        self.score = score
        self.severity_bucket = severity_bucket
        self.reasons = reasons


class ClassifierService:
    def __init__(self, catalog: SourceCatalog) -> None:
        self.catalog = catalog

    def classify(self, record: CollectedRecord) -> ClassificationResult:
        score = 0
        reasons: list[str] = []
        haystack = " ".join([record.title, record.summary, " ".join(record.keywords)]).lower()

        confirmed_rule = self.catalog.config.keyword_rules.get("confirmed_security")
        high_rule = self.catalog.config.keyword_rules.get("security_candidate_high")
        medium_rule = self.catalog.config.keyword_rules.get("security_candidate_medium")

        confirmed_sources = set(confirmed_rule.sources if confirmed_rule else [])
        high_keywords = high_rule.subject_or_body_any if high_rule else []
        medium_keywords = medium_rule.subject_or_body_any if medium_rule else []

        if record.source_id in confirmed_sources:
            score += 100
            reasons.append("official confirmed security source")

        if record.cve_ids or "cve-" in haystack:
            score += 40
            reasons.append("cve indicator")

        for keyword in high_keywords:
            lowered = keyword.lower()
            if lowered in haystack:
                score += 25
                reasons.append(f"keyword:{lowered}")

        for keyword in medium_keywords:
            lowered = keyword.lower()
            if lowered in haystack:
                score += 15
                reasons.append(f"context:{lowered}")

        if "critical" in haystack:
            score += 20
            reasons.append("severity:critical")
        elif "high" in haystack:
            score += 10
            reasons.append("severity:high")

        if score >= 100:
            bucket = "confirmed_security"
        elif score >= 60:
            bucket = "security_candidate_high"
        elif score > 0:
            bucket = "security_candidate_medium"
        elif record.kind == "release":
            bucket = "release_only"
        else:
            bucket = "general_patch"

        return ClassificationResult(score=score, severity_bucket=bucket, reasons=reasons)
