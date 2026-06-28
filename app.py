from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import smtplib
import subprocess
import tempfile
import textwrap
import unicodedata
import webbrowser
from email.message import EmailMessage
from html import unescape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PORT = int(os.environ.get("PORT", "8080"))
HOST = os.environ.get("HOST", "127.0.0.1")
ROOT = Path(__file__).resolve().parent
HTML_FILE = ROOT / "simulador.html"
SMTP_CONFIG_FILE = Path(os.environ.get("SMTP_CONFIG_FILE", ROOT / "smtp_config.json"))


def response(status: int, content: bytes, content_type: str) -> tuple[int, bytes, str]:
    return status, content, content_type


def json_response(status: int, payload: dict[str, object]) -> tuple[int, bytes, str]:
    return response(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")


def get_content(path: str) -> tuple[int, bytes, str]:
    parsed_path = unquote(urlparse(path).path)
    if parsed_path in {"/", "/index.html", "/simulador.html"}:
        if not HTML_FILE.exists():
            return response(404, b"simulador.html nao encontrado", "text/plain; charset=utf-8")
        return response(200, HTML_FILE.read_bytes(), "text/html; charset=utf-8")

    target = (ROOT / parsed_path.lstrip("/")).resolve()
    if ROOT not in target.parents or not target.is_file():
        return response(404, b"Nao encontrado", "text/plain; charset=utf-8")
    content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return response(200, target.read_bytes(), content_type)


def send_email_payload(body: bytes) -> tuple[int, bytes, str]:
    try:
        payload = json.loads(body.decode("utf-8") if body else "{}")
        email = str(payload.get("email", "")).strip()
        html = str(payload.get("html", "")).strip()
        text = str(payload.get("text", "")).strip()
        if "@" not in email or "." not in email:
            return json_response(400, {"ok": False, "error": "E-mail invalido."})
        if not html and not text:
            return json_response(400, {"ok": False, "error": "Conteudo da simulacao nao informado."})

        pdf = generate_pdf(html, text)
        send_email_with_pdf(email, pdf)
        return json_response(200, {"ok": True})
    except Exception as exc:
        return json_response(500, {"ok": False, "error": str(exc)})


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, content, "application/json; charset=utf-8")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        status, content, content_type = get_content(self.path)
        self._send(status, content, content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/send-email":
            self._send_json(404, {"ok": False, "error": "Endpoint nao encontrado."})
            return

        length = int(self.headers.get("Content-Length", "0"))
        status, content, content_type = send_email_payload(self.rfile.read(length))
        self._send(status, content, content_type)

    def log_message(self, format: str, *args: object) -> None:
        return


def find_browser() -> str | None:
    candidates = [
        os.environ.get("CHROME_BIN"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        shutil.which("chrome"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("msedge"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def generate_pdf(html: str, text: str = "") -> bytes:
    if html:
        pdf = generate_browser_pdf(html)
        if pdf:
            return pdf
    if text:
        return generate_text_pdf_from_text(text)
    return generate_text_pdf(html)


def generate_browser_pdf(html: str) -> bytes:
    browser = find_browser()
    if not browser:
        return b""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        html_file = temp_path / "simulacao.html"
        pdf_file = temp_path / "simulacao.pdf"
        profile_dir = temp_path / "browser-profile"
        html_file.write_text(html, encoding="utf-8")

        command = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-gpu",
            "--disable-gpu-compositing",
            "--disable-gpu-sandbox",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-features=UseDawn,SkiaGraphite,DawnGraphite,Vulkan,VizDisplayCompositor",
            "--no-first-run",
            "--no-default-browser-check",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=2500",
            f"--user-data-dir={profile_dir}",
            "--print-to-pdf-no-header",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_file}",
            html_file.as_uri(),
        ]
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        except subprocess.TimeoutExpired:
            return b""
        if result.returncode != 0 or not pdf_file.exists():
            return b""
        return pdf_file.read_bytes()


class PlainTextExtractor(HTMLParser):
    block_tags = {
        "address",
        "article",
        "aside",
        "br",
        "caption",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self.skip_depth += 1
            return
        if tag in self.block_tags:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append("  ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        clean = re.sub(r"\s+", " ", unescape(data)).strip()
        if clean:
            self.parts.append(clean + " ")

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    parser = PlainTextExtractor()
    parser.feed(html)
    text = parser.text()
    return text or "Simulacao sem conteudo textual disponivel."


def pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_text(value: str) -> str:
    clean = value.replace("€", "EUR").replace("–", "-").replace("—", "-")
    clean = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii")
    return pdf_escape(clean)


def generate_text_pdf(html: str) -> bytes:
    return generate_text_pdf_from_text(html_to_text(html))


def generate_text_pdf_from_text(text: str) -> bytes:
    one_page = text.startswith("ONE_PAGE")
    if one_page:
        text = text.removeprefix("ONE_PAGE").lstrip()
        return generate_one_page_report_pdf(text)
    page_width = 841.89
    page_height = 595.28
    margin = 36
    line_height = 12
    font_size = 9
    wrapped: list[str] = []
    for line in text.splitlines():
        wrapped.extend(textwrap.wrap(line, width=138 if one_page else 125) or [""])

    if one_page and wrapped:
        available_height = page_height - 110
        line_height = max(7.2, min(11, available_height / max(1, len(wrapped))))
        font_size = max(5.8, min(8.5, line_height - 1.2))
        pages = [wrapped]
    else:
        lines_per_page = int((page_height - 110) // line_height)
        pages = [wrapped[index : index + lines_per_page] for index in range(0, len(wrapped), lines_per_page)]

    if not pages:
        pages = [["Simulacao sem conteudo textual disponivel."]]

    objects: list[bytes] = []
    page_count = len(pages)
    font_obj_id = 3 + (page_count * 2)
    page_ids = [3 + (index * 2) for index in range(page_count)]
    content_ids = [4 + (index * 2) for index in range(page_count)]

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {page_count} >>".encode(
            "latin-1"
        )
    )

    for page_index, page_lines in enumerate(pages):
        content_id = content_ids[page_index]
        page_id = page_ids[page_index]
        stream_lines = [
            "BT",
            f"/F1 16 Tf 1 0 0 1 {margin} {page_height - margin} Tm (Simulacao de Custo Contrato VS Freelancer) Tj",
            f"/F1 {font_size:.2f} Tf 1 0 0 1 {margin} {page_height - margin - 28} Tm",
        ]
        for line in page_lines:
            stream_lines.append(f"({pdf_text(line[:150])}) Tj")
            stream_lines.append(f"0 -{line_height} Td")
        footer = "Desenvolvido por Felipe Manso Consultor SAP LO (MM/SD) - www.linkedin.com/in/sapfelipemanso"
        stream_lines.extend(
            [
                "ET",
                "BT",
                f"/F1 8 Tf 1 0 0 1 {margin} 24 Tm ({pdf_text(footer)}) Tj",
                "ET",
            ]
        )
        stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("latin-1")
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("latin-1"))
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")

    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_position}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(pdf)


def split_report_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"intro": []}
    current = "intro"
    known = {
        "Parametros principais",
        "Resultados",
        "Taxa dia informada",
        "Tabela rapida por taxa dia",
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line in known:
            current = line
            sections[current] = []
            continue
        sections.setdefault(current, []).append(line)
    return sections


def generate_one_page_report_pdf(text: str) -> bytes:
    page_width = 841.89
    page_height = 595.28
    margin = 12
    content: list[str] = []

    def rect(x: float, y: float, w: float, h: float, shade: str = "0.93 0.97 0.99") -> None:
        content.append(f"q {shade} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f Q")
        content.append(f"q 0.70 0.80 0.87 RG {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S Q")

    def line(x1: float, y1: float, x2: float, y2: float) -> None:
        content.append(f"q 0.73 0.82 0.88 RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q")

    def text_at(x: float, y: float, value: str, size: float = 8, bold: bool = False) -> None:
        font = "F2" if bold else "F1"
        content.append(f"BT /{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({pdf_text(value)}) Tj ET")

    def section_title(title: str, x: float, y: float, w: float) -> float:
        rect(x, y - 3, w, 18, "0.86 0.93 0.97")
        text_at(x + 8, y + 3, title, 12.4, True)
        return y - 16

    def draw_table(title: str, rows: list[str], x: float, y: float, w: float) -> float:
        if not rows:
            return y
        y = section_title(title, x, y, w)
        parsed = [row.split("|") for row in rows if "|" in row]
        if not parsed:
            return y
        headers = [cell.strip() for cell in parsed[0]]
        body = [[cell.strip() for cell in row] for row in parsed[1:]]
        widths = [46, 70, 96, 84, 82, 82, 100, 100, 106]
        scale = w / sum(widths)
        widths = [item * scale for item in widths]
        row_h = 18
        table_h = row_h * (len(body) + 1)
        rect(x, y - table_h + 2, w, table_h, "0.98 0.99 1.00")
        rect(x, y - row_h + 2, w, row_h, "0.82 0.91 0.96")
        cursor = x
        for index, width in enumerate(widths):
            if index:
                line(cursor, y + 2, cursor, y - table_h + 2)
            label = headers[index] if index < len(headers) else ""
            text_at(cursor + 3, y - 11, label[:16], 9.2, True)
            cursor += width
        line(x, y - row_h + 2, x + w, y - row_h + 2)
        for row_index, row in enumerate(body):
            row_y = y - row_h * (row_index + 1)
            cursor = x
            for index, width in enumerate(widths):
                value = row[index] if index < len(row) else ""
                size = 8.5 if index >= 2 else 8.8
                text_at(cursor + 3, row_y - 12, value[:20], size, index == 0)
                cursor += width
            line(x, row_y - row_h + 2, x + w, row_y - row_h + 2)
        return y - table_h - 14

    sections = split_report_sections(text)
    title = sections.get("intro", ["Simulador Salarial Portugal 2026", "Freelancer vs Contrato"])
    text_at(margin, page_height - 34, title[1] if len(title) > 1 else "Freelancer vs Contrato", 29, True)
    content.append(f"q 0.95 0.62 0.10 rg {margin:.2f} {page_height - 58:.2f} 190 16 re f Q")
    text_at(margin + 8, page_height - 54, "Recibos verdes, IVA, IRS Cat. B e Seguranca Social TI", 9.8, True)

    y = page_height - 82
    left_w = 210
    right_x = margin + left_w + 10
    right_w = page_width - right_x - margin

    y_left = section_title("Parametros principais", margin, y, left_w)
    for item in sections.get("Parametros principais", []):
        for part in [piece.strip() for piece in item.split("|") if piece.strip()]:
            text_at(margin + 8, y_left, part, 9.5)
            y_left -= 13

    result_lines = sections.get("Resultados", [])
    kpi_parts: list[str] = []
    formula_parts: list[str] = []
    for item in result_lines:
        if item.startswith("Calculo"):
            formula_parts.append(item)
        else:
            kpi_parts.extend([piece.strip() for piece in item.split("|") if piece.strip()])

    card_gap = 10
    card_w = (right_w - card_gap) / 2
    card_h = 54
    for index, item in enumerate(kpi_parts[:2]):
        x = right_x + (card_w + card_gap) * index
        rect(x, y - card_h + 12, card_w, card_h, "0.98 0.99 1.00")
        label, _, value = item.partition(":")
        text_at(x + 10, y - 2, label.strip(), 10.4, True)
        text_at(x + 10, y - 28, value.strip(), 21.5, True)
    if len(kpi_parts) > 2:
        for index, item in enumerate(kpi_parts[2:4]):
            x = right_x + (card_w + card_gap) * index
            label, _, value = item.partition(":")
            text_at(x + 10, y - 46, f"{label.strip()}: {value.strip()}", 10.0, True)

    formula_y = y - card_h - 9
    formula_h = 52
    rect(right_x, formula_y - formula_h + 12, right_w, formula_h, "0.98 0.99 1.00")
    text_at(right_x + 8, formula_y - 1, "Calculo da Diferenca", 12.4, True)
    formula_text = formula_parts[0] if formula_parts else ""
    for offset, wrapped in enumerate(textwrap.wrap(formula_text, width=95)[:3]):
        text_at(right_x + 8, formula_y - 18 - (offset * 11), wrapped, 9.2)

    y_right = formula_y - formula_h - 8
    y_tables = min(y_left, y_right) - 6
    y_tables = draw_table("Taxa dia informada", sections.get("Taxa dia informada", []), margin, y_tables, page_width - (2 * margin))
    y_tables = draw_table("Tabela rapida por taxa dia", sections.get("Tabela rapida por taxa dia", []), margin, y_tables, page_width - (2 * margin))

    footer = "Desenvolvido por Felipe Manso Consultor SAP LO (MM/SD) - www.linkedin.com/in/sapfelipemanso"
    line(margin, 34, page_width - margin, 34)
    text_at(margin, 22, footer, 7.6)

    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>"
        ).encode("latin-1"),
        f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_id} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_position}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(pdf)


def load_smtp_config() -> dict[str, str]:
    config: dict[str, str] = {}
    if SMTP_CONFIG_FILE.exists():
        try:
            loaded = json.loads(SMTP_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config = {str(key).upper(): str(value) for key, value in loaded.items()}
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Arquivo smtp_config.json invalido: {exc}") from exc
    return config


def smtp_value(config: dict[str, str], key: str, default: str = "") -> str:
    return os.environ.get(key, config.get(key, default))


def send_email_with_pdf(recipient: str, pdf: bytes) -> None:
    config = load_smtp_config()
    host = smtp_value(config, "SMTP_HOST").strip()
    port = int(smtp_value(config, "SMTP_PORT", "587"))
    user = smtp_value(config, "SMTP_USER").strip()
    password = smtp_value(config, "SMTP_PASS")
    sender = smtp_value(config, "SMTP_FROM", user).strip()
    use_ssl = smtp_value(config, "SMTP_SSL").lower() in {"1", "true", "yes"} or port == 465
    use_tls = smtp_value(config, "SMTP_TLS", "true").lower() not in {"0", "false", "no"}

    if not host or not sender:
        raise RuntimeError(
            "Configure o arquivo smtp_config.json com SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS e SMTP_FROM."
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "Comparação – Contrato vs Freelancer em Portugal"
    message.set_content(
        """Olá,

Espero que esteja tudo bem.

Compartilho consigo o resultado da ferramenta que desenvolvi para auxiliar profissionais na análise de propostas de trabalho em Portugal.

A planilha permite comparar, de forma prática, diferentes cenários entre contrato de trabalho e prestação de serviços (freelancer), considerando aspetos como remuneração líquida, encargos, impostos e outros fatores que muitas vezes passam despercebidos durante uma negociação.

O objetivo é proporcionar uma visão mais clara do impacto financeiro de cada opção, permitindo decisões mais informadas e conscientes.

Caso considere útil, ficarei muito satisfeito em receber o seu feedback ou sugestões de melhoria.

Aproveito também para o convidar a conhecer o meu perfil profissional no LinkedIn, onde partilho regularmente conteúdos sobre SAP S/4HANA, transformação digital, metodologias de implementação, carreira em tecnologia e gestão de projetos:

LinkedIn: www.linkedin.com/in/sapfelipemanso

Espero que este material lhe seja útil e agradeço desde já a sua atenção.

Com os melhores cumprimentos,

Felipe Manso
SAP Logistics Consultant (MM/SD) | SAP S/4HANA"""
    )
    message.add_attachment(
        pdf,
        maintype="application",
        subtype="pdf",
        filename="simulacao-contrato-vs-freelancer.pdf",
    )

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=30) as smtp:
        if not use_ssl and use_tls:
            smtp.starttls()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)


def application(environ: dict[str, object], start_response) -> list[bytes]:
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    path = str(environ.get("PATH_INFO", "/"))
    query = str(environ.get("QUERY_STRING", ""))
    full_path = f"{path}?{query}" if query else path

    if method == "OPTIONS":
        status, content, content_type = 204, b"", "text/plain; charset=utf-8"
    elif method == "GET":
        status, content, content_type = get_content(full_path)
    elif method == "POST" and path == "/send-email":
        try:
            length = int(str(environ.get("CONTENT_LENGTH") or "0"))
        except ValueError:
            length = 0
        body = environ["wsgi.input"].read(length) if length else b""
        status, content, content_type = send_email_payload(body)
    else:
        status, content, content_type = json_response(404, {"ok": False, "error": "Endpoint nao encontrado."})

    reason = {
        200: "OK",
        204: "No Content",
        400: "Bad Request",
        404: "Not Found",
        500: "Internal Server Error",
    }.get(status, "OK")
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(content))),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
    ]
    start_response(f"{status} {reason}", headers)
    return [content]


def main() -> int:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"Servidor iniciado em {url}")
    if os.environ.get("OPEN_BROWSER", "1").lower() not in {"0", "false", "no"}:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
