#!/bin/env python3
'''Modified version of QTableWidget that allows to copy and paste content in tab-separated format.'''

from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QShortcut
from PyQt5.QtGui import QKeySequence
from PyQt5.QtCore import Qt

class CopyPasteTableWidget(QTableWidget):

    def __init__(self, parent=None):

        super().__init__(parent)

        # Set up copy and paste shortcuts
        self.copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        self.copy_shortcut.activated.connect(self.copy_selection)

        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.activated.connect(self.paste_selection)

    def copy_selection(self):

        # Get selected range of cells
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            return

        # Build a string to represent the copied data
        copied_text = ""
        for selected_range in selected_ranges:
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                row_data = []
                for col in range(selected_range.leftColumn(), selected_range.rightColumn() + 1):
                    item = self.item(row, col)
                    row_data.append(item.text() if item else "")
                copied_text += "\t".join(row_data) + "\n"

        # Copy to clipboard
        QApplication.clipboard().setText(copied_text)

    def paste_selection(self):
        # Get clipboard text
        clipboard_text = QApplication.clipboard().text()

        # Split the clipboard data by rows and columns (assuming tab-separated)
        rows = clipboard_text.split("\n")
        current_row = self.currentRow()
        current_col = self.currentColumn()

        # Iterate through rows and columns from clipboard
        for i, row_data in enumerate(rows):
            if not row_data.strip():
                continue

            cells = row_data.split("\t")
            for j, cell_value in enumerate(cells):
                target_row = current_row + i
                target_col = current_col + j

                if target_row < self.rowCount() and target_col < self.columnCount():
                    item = QTableWidgetItem(cell_value)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.setItem(target_row, target_col, item)
