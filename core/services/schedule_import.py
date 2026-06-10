import pandas as pd
from django.utils import timezone
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import ZipFile

from core.models import PostSchedule


def import_schedule_file(file_path):
    if file_path.lower().endswith(("xls", "xlsx")):
        try:
            dataframe = pd.read_excel(file_path)
        except ImportError:
            dataframe = _read_xlsx_without_openpyxl(file_path)
    else:
        dataframe = pd.read_csv(file_path)

    dataframe.columns = [str(column).strip().lower() for column in dataframe.columns]

    created_count = 0
    for _, row in dataframe.iterrows():
        topic = row.get("topic")
        if pd.isna(topic) or not str(topic).strip():
            continue

        scheduled_date = _parse_schedule_date(row.get("date"))
        if pd.isna(scheduled_date):
            scheduled_date = timezone.now()
        elif timezone.is_naive(scheduled_date):
            scheduled_date = timezone.make_aware(scheduled_date.to_pydatetime())

        PostSchedule.objects.create(
            date=scheduled_date,
            topic=str(topic).strip(),
            tone=_clean_cell(row.get("tone"), "Professional"),
            category=_first_clean_cell([row.get("audience"), row.get("category")], "General"),
            platform=_clean_cell(row.get("platform"), "LinkedIn"),
            priority=_clean_cell(row.get("priority"), "Medium"),
            status="draft",
        )
        created_count += 1

    return created_count


def _clean_cell(value, fallback):
    if pd.isna(value) or not str(value).strip():
        return fallback
    return str(value).strip()


def _first_clean_cell(values, fallback):
    for value in values:
        cleaned = _clean_cell(value, "")
        if cleaned:
            return cleaned
    return fallback


def _parse_schedule_date(value):
    if isinstance(value, (int, float)) and not pd.isna(value):
        return pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
    return pd.to_datetime(value, errors="coerce")


def _read_xlsx_without_openpyxl(file_path):
    namespace = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
        "office_rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with ZipFile(file_path) as workbook:
        shared_strings = _read_shared_strings(workbook, namespace)
        sheet_path = _get_first_sheet_path(workbook, namespace)
        sheet_xml = workbook.read(sheet_path)

    root = ElementTree.fromstring(sheet_xml)
    rows = []
    for row in root.findall(".//main:sheetData/main:row", namespace):
        values_by_column = {}
        for cell in row.findall("main:c", namespace):
            column_index = _column_index_from_cell_ref(cell.attrib.get("r", ""))
            if column_index is None:
                column_index = len(values_by_column)
            values_by_column[column_index] = _read_cell_value(cell, shared_strings, namespace)
        if values_by_column:
            max_column = max(values_by_column)
            rows.append([values_by_column.get(index, "") for index in range(max_column + 1)])

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows[1:], columns=rows[0])


def _read_shared_strings(workbook, namespace):
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []

    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("main:si", namespace):
        text_parts = [node.text or "" for node in item.findall(".//main:t", namespace)]
        values.append("".join(text_parts))
    return values


def _get_first_sheet_path(workbook, namespace):
    if "xl/workbook.xml" not in workbook.namelist():
        return "xl/worksheets/sheet1.xml"

    workbook_root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
    first_sheet = workbook_root.find(".//main:sheets/main:sheet", namespace)
    if first_sheet is None or "xl/_rels/workbook.xml.rels" not in workbook.namelist():
        return "xl/worksheets/sheet1.xml"

    relationship_id = first_sheet.attrib.get(f"{{{namespace['office_rel']}}}id")
    relationships_root = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships_root.findall("rel:Relationship", namespace):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target", "worksheets/sheet1.xml")
            return str(PurePosixPath("xl") / target)
    return "xl/worksheets/sheet1.xml"


def _read_cell_value(cell, shared_strings, namespace):
    inline_text = cell.find("main:is/main:t", namespace)
    if inline_text is not None:
        return inline_text.text or ""

    value_node = cell.find("main:v", namespace)
    if value_node is None or value_node.text is None:
        return ""

    value = value_node.text
    if cell.attrib.get("t") == "s":
        index = int(value)
        return shared_strings[index] if index < len(shared_strings) else ""
    return value


def _column_index_from_cell_ref(cell_ref):
    letters = "".join(character for character in cell_ref if character.isalpha())
    if not letters:
        return None

    column_index = 0
    for character in letters.upper():
        column_index = column_index * 26 + ord(character) - ord("A") + 1
    return column_index - 1
