if __name__ == '__main__':
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    # Create workbook and multiple sheets to break Rule 1
    wb = openpyxl.Workbook()

    # Sheet 1: Main data starting away from column A (breaking Rule 6), mixed headers (breaking Rule 7), mixed data rows (breaking Rule 8), merged headers, colors for data status (breaking Rule 9)
    ws1 = wb.active
    ws1.title = "Q1_Financial_Report"

    # Break Rule 6: Start table in column C instead of column A
    # Break Rule 7: Column headers are NOT the first row (rows 1-3 are empty/title blocks)
    ws1['C1'] = "CONFIDENTIAL INTERNAL REPORT - DO NOT DISTRIBUTE"
    ws1['C2'] = "Fiscal Year 2026 - Q1 Summary (Updated by J. Smith)"
    ws1['C3'] = "" # Blank spacer

    # Actual headers placed at row 5 (breaking Rule 7)
    headers = ["Region_Code", "Item Description", "QTY", "Unit_Price", "Status_Flag"]
    for col_idx, header in enumerate(headers, start=3): # Start at col C (3)
        cell = ws1.cell(row=5, column=col_idx, value=header)
        cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Data rows starting at row 7 instead of row 2 (breaking Rule 8)
    # Break Rule 2: Mixed casing in columns (Region_Code vs Item Description vs QTY)
    # Break Rule 3: Lowercase/mixed string text instead of UPPERCASE
    # Break Rule 4: Mixed data types in single column (numbers and text strings)
    # Break Rule 5: Multiple values in single cell (e.g., "12, 14, 18 (Batch B)") violating 1NF
    # Break Rule 9: Using background colors to encode data status (red/green fills) instead of a dedicated column
    data = [
        ("north", "Widget A (Deluxe Edition)", "12, 14, 18 (Batch B)", 45.50, "urgent"),
        ("SOUTH", "Gadget X", 25, "Call for Quote", "Normal"),
        ("east", "Part #9921 - Bolt & Nut Set", 100, 1.25, "OK"),
        ("WEST", "Service Fee (Consulting)", "N/A", 1500.00, "PENDING"),
        ("North", "Widget B / C Combo Pack", 50, 89.99, "URGENT")
    ]

    red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
    green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    row_idx = 7 # Break Rule 8
    for item in data:
        for col_idx, val in enumerate(item, start=3):
            cell = ws1.cell(row=row_idx, column=col_idx, value=val)
            
            # Break Rule 9: Colors for data status
            if col_idx == 7: # Status_Flag column
                if val in ["urgent", "URGENT"]:
                    cell.fill = red_fill
                elif val in ["OK", "Normal"]:
                    cell.fill = green_fill
                else:
                    cell.fill = yellow_fill
                    
        row_idx += 1

    # Add a summary row with merged cells inside the data block (breaking normalization & table structure rules)
    ws1.merge_cells('C13:E13')
    summary_cell = ws1.cell(row=13, column=3, value="TOTAL COMBINED REVENUE & METRICS")
    summary_cell.font = Font(name="Calibri", bold=True)
    summary_cell.alignment = Alignment(horizontal="right")

    val_cell = ws1.cell(row=13, column=6, value="=SUM(F8:F11)") # Formula referencing unaligned range
    val_cell.font = Font(name="Calibri", bold=True)

    # Sheet 2: Another sheet (Breaking Rule 1)
    ws2 = wb.create_sheet(title="Q2_Projections")
    ws2['A1'] = "Quarter 2 Projections (See Sheet 1 for notes)"
    ws2['A3'] = "Category"
    ws2['B3'] = "Forecast"
    ws2['A4'] = "Hardware"
    ws2['B4'] = 50000

    # Sheet 3: Yet another sheet with pivot-like fractured layout (Breaking Rule 1)
    ws3 = wb.create_sheet(title="Metadata_Log")
    ws3['B2'] = "Log Date:"
    ws3['C2'] = "2026-10-23"
    ws3['B4'] = "Author:"
    ws3['C4'] = "Admin"

    # Save file
    file_path = "broken_table_structure_example.xlsx"
    wb.save(file_path)
    print(f"File saved successfully as {file_path}")