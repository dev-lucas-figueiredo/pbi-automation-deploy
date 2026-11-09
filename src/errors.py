"""Erros e parsing de respostas das APIs Fabric / Power BI."""

import json


class APIError(Exception):
    """Erro estruturado da Fabric API com todos os campos relevantes para diagnostico."""

    def __init__(self, action, status_code, body, headers=None, url=None):
        self.action = action
        self.status_code = status_code
        self.body = body or ""
        self.headers = headers or {}
        self.url = url
        super().__init__(self._format())

    def _format(self):
        request_id = (
            self.headers.get("RequestId")
            or self.headers.get("x-ms-request-id")
            or self.headers.get("requestid")
        )
        error_code_header = self.headers.get("x-ms-public-api-error-code")

        msg_estruturada = ""
        codigo_estruturado = ""
        try:
            parsed = json.loads(self.body) if self.body else {}
            msg_estruturada = (
                parsed.get("message")
                or parsed.get("error", {}).get("message")
                or ""
            )
            codigo_estruturado = (
                parsed.get("errorCode")
                or parsed.get("error", {}).get("code")
                or ""
            )
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        partes = [f"HTTP {self.status_code}"]
        if codigo_estruturado or error_code_header:
            partes.append(f"code={codigo_estruturado or error_code_header}")
        if request_id:
            partes.append(f"reqId={request_id[:13]}")

        detalhe = msg_estruturada or (self.body[:240] if self.body else "[body vazio]")
        return f"{self.action} | {' | '.join(partes)} | {detalhe}"


def parse_body_safe(response):
    """Tenta extrair JSON do response sem quebrar com 'null', vazio ou texto invalido."""
    if not response.text or not response.text.strip():
        return None
    try:
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None
