from __future__ import annotations

import html
import re
import sys
import zipfile
from pathlib import Path


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""


RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


DOCUMENT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>
        <w:sz w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="32"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="28"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="24"/>
    </w:rPr>
  </w:style>
</w:styles>
"""


def clean_inline_markdown(text: str) -> str:
    text = text.replace("`", "")
    text = text.replace("**", "")
    text = text.replace("*", "")
    text = text.replace("_", "")
    return text.strip()


def xml_text(text: str) -> str:
    return html.escape(text, quote=False)


def paragraph_xml(text: str, style: str | None = None) -> str:
    safe_text = xml_text(text)
    style_xml = ""
    if style:
        style_xml = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>"
    return (
        "<w:p>"
        f"{style_xml}"
        "<w:r><w:t xml:space=\"preserve\">"
        f"{safe_text}"
        "</w:t></w:r>"
        "</w:p>"
    )


def build_document_xml(markdown_text: str) -> str:
    body_parts: list[str] = []
    in_code_block = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            body_parts.append(paragraph_xml(clean_inline_markdown(line)))
            continue

        stripped = line.strip()
        if not stripped:
            body_parts.append(paragraph_xml(""))
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = clean_inline_markdown(heading_match.group(2))
            body_parts.append(paragraph_xml(heading_text, style=f"Heading{level}"))
            continue

        if stripped.startswith("- "):
            bullet_text = clean_inline_markdown(stripped[2:])
            body_parts.append(paragraph_xml(f"• {bullet_text}"))
            continue

        if re.match(r"^\d+\.\s+", stripped):
            number_text = clean_inline_markdown(stripped)
            body_parts.append(paragraph_xml(number_text))
            continue

        body_parts.append(paragraph_xml(clean_inline_markdown(stripped)))

    section_props = (
        "<w:sectPr>"
        "<w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" "
        "w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>"
        "</w:sectPr>"
    )
    body_xml = "".join(body_parts) + section_props
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{body_xml}</w:body>"
        "</w:document>"
    )


def convert_markdown_to_docx(source: Path, target: Path) -> None:
    document_xml = build_document_xml(source.read_text(encoding="utf-8"))

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        docx.writestr("_rels/.rels", RELS_XML)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", STYLES_XML)
        docx.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS_XML)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/md_to_docx.py <source.md> <target.docx>")
        return 1

    source = Path(sys.argv[1]).resolve()
    target = Path(sys.argv[2]).resolve()
    convert_markdown_to_docx(source, target)
    print(f"Wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
