# -*- coding: utf-8 -*-
"""
Excel (.xlsx) generator yordamchi moduli - Kafel Center Savdo & Ombor Tizimi
openpyxl kutubxonasi yordamida chiroyli, formatlangan va tayyor Excel fayllarini hosil qiladi.
"""

import io
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Ranglar palitrasi
NAVY_HEADER = "1E293B"      # Slate 800
ACCENT_BLUE = "0284C7"      # Sky 600
TEXT_WHITE = "FFFFFF"
ROW_BG_EVEN = "F8FAFC"      # Slate 50
ROW_BG_ODD = "FFFFFF"
BORDER_GRAY = "E2E8F0"      # Slate 200

def create_styled_excel(
    sheet_title: str,
    report_title: str,
    headers: list,
    data_rows: list,
    user_name: str = "Tizim",
    user_role: str = "admin",
    column_formats: dict = None
) -> io.BytesIO:
    """
    Standartlashtirilgan, professional bezatilgan Excel (.xlsx) faylini yaratadi.
    
    :param sheet_title: Excel varag'i nomi (maks 31 belgi)
    :param report_title: Hisobot sarlavhasi (masalan, 'Ombor Qoldiqlari Hisoboti')
    :param headers: Ustun nomlari ro'yxati ['SKU', 'Marka', 'Hajmi (m²)', ...]
    :param data_rows: Qatorlar ro'yxati [[val1, val2, ...], ...]
    :param user_name: Eksport qilgan xodim ismi
    :param user_role: Xodim roli
    :param column_formats: Har bir ustun uchun format turi {col_index: 'currency'|'sqm'|'int'|'pct'|'center'|'right'}
    :return: io.BytesIO obyekti
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (sheet_title[:28] if len(sheet_title) > 28 else sheet_title) or "Hisobot"

    # Set grid lines visible
    ws.views.sheetView[0].showGridLines = True

    # Chegara stillari
    thin_border = Border(
        left=Side(style='thin', color=BORDER_GRAY),
        right=Side(style='thin', color=BORDER_GRAY),
        top=Side(style='thin', color=BORDER_GRAY),
        bottom=Side(style='thin', color=BORDER_GRAY)
    )
    header_border = Border(
        left=Side(style='thin', color="334155"),
        right=Side(style='thin', color="334155"),
        top=Side(style='medium', color="0F172A"),
        bottom=Side(style='medium', color="0F172A")
    )

    # 1. Kompaniya brendi (1-qator)
    ws.cell(row=1, column=1, value="KAFEL CENTER & SAVDO TIZIMI")
    ws.cell(row=1, column=1).font = Font(name='Calibri', size=14, bold=True, color="0F172A")

    # 2. Hisobot Sarlavhasi (2-qator)
    ws.cell(row=2, column=1, value=report_title)
    ws.cell(row=2, column=1).font = Font(name='Calibri', size=12, bold=True, color=ACCENT_BLUE)

    # 3. Meta ma'lumotlar (3-qator)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_text = f"Eksport vaqti: {now_str} | Mas'ul xodim: {user_name} ({user_role.upper()})"
    ws.cell(row=3, column=1, value=meta_text)
    ws.cell(row=3, column=1).font = Font(name='Calibri', size=9, italic=True, color="64748B")

    # 4-qator bo'sh qoldiriladi

    # 5. Jadvallar Sarlavhasi (Headers)
    header_row_idx = 5
    header_font = Font(name='Calibri', size=10, bold=True, color=TEXT_WHITE)
    header_fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")

    column_formats = column_formats or {}

    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=str(h))
        cell.font = header_font
        cell.fill = header_fill
        cell.border = header_border
        
        # Ustun sarlavhasi hizalanishi
        align = "center"
        fmt = column_formats.get(col_idx - 1, "")
        if fmt in ["currency", "sqm", "right"]:
            align = "right"
        elif fmt in ["left"]:
            align = "left"
        cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=True)

    ws.row_dimensions[header_row_idx].height = 26

    # 6. Ma'lumotlar qatorlari
    current_row = 6
    for row_data in data_rows:
        bg_color = ROW_BG_EVEN if (current_row % 2 == 0) else ROW_BG_ODD
        row_fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")

        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = thin_border
            cell.fill = row_fill
            cell.font = Font(name='Calibri', size=10, color="1E293B")

            fmt = column_formats.get(col_idx - 1, "")

            # Qiymatni formatlash va qo'yish
            if val is None or val == "":
                cell.value = ""
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif fmt == "currency":
                try:
                    num_val = float(val)
                    cell.value = num_val
                    cell.number_format = '#,##0 "so\'m"'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif fmt == "sqm":
                try:
                    num_val = float(val)
                    cell.value = num_val
                    cell.number_format = '0.00 "m²"'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif fmt == "int":
                try:
                    num_val = int(round(float(val)))
                    cell.value = num_val
                    cell.number_format = '#,##0'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif fmt == "pct":
                try:
                    num_val = float(val)
                    cell.value = num_val
                    cell.number_format = '0.0"%"'
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                except (ValueError, TypeError):
                    cell.value = str(val)
                    cell.alignment = Alignment(horizontal="right", vertical="center")
            elif fmt == "center":
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif fmt == "right":
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                # Oddiy matn yoki sana
                cell.value = str(val)
                cell.alignment = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    # Qatorlar oxiriga yakuniy chiziq
    if data_rows:
        last_row = current_row - 1
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=last_row, column=col_idx)
            c.border = Border(
                left=Side(style='thin', color=BORDER_GRAY),
                right=Side(style='thin', color=BORDER_GRAY),
                top=Side(style='thin', color=BORDER_GRAY),
                bottom=Side(style='medium', color="475569")
            )

    # 7. Ustunlar kengligini avtomatik hisoblash
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(headers[col_idx - 1]))
        
        # Qatorlar ichidagi maksimal uzunlikni tekshirish
        sample_rows = data_rows[:100]
        for r in sample_rows:
            if col_idx - 1 < len(r):
                v_str = str(r[col_idx - 1] or "")
                if len(v_str) > max_len:
                    max_len = len(v_str)

        # Min va Max kenglik chegarasi
        adjusted_width = max(max_len + 4, 12)
        adjusted_width = min(adjusted_width, 55)
        ws.column_dimensions[col_letter].width = adjusted_width

    # Birinchi 5 ta qatorni qotirib qo'yish (Freeze panes)
    ws.freeze_panes = "A6"

    # Faylni xotirada saqlash
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
