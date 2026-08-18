# -*- coding: utf-8 -*-
"""
facet_filter.py
---------------
Column filters for the search panel.

Pick a column, get a drop-down of the values that actually occur in it, and
check one or more. Several column filters can be active at once:

    within one column   -> OR   (value A or value B)
    between columns     -> AND  (... and a given value in another column)

The value lists cascade: each drop-down only shows the values still possible
once the other filters are applied. The number in brackets is the row count.

User interface texts are English in the source and translated through i18n/.

Where a field has a value map, the displayed text is shown ("Grazing") while
filtering happens on the stored value ("graesning"). Two codes can share the
same displayed text, and the code is then added in square brackets so they can
be told apart and filtered separately.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal, QCoreApplication
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QPalette
from qgis.PyQt.QtWidgets import (
    QWidget, QComboBox, QHBoxLayout, QVBoxLayout, QLabel, QToolButton,
    QStylePainter, QStyle, QStyleOptionComboBox, QSizePolicy, QFrame,
)

VALUE_ROLE = Qt.UserRole + 1

# marks the row at the top of the drop-down that checks every value at once
ALL_ROLE = Qt.UserRole + 2

def _tr(text):
    """Translate a string used outside a QObject."""
    return QCoreApplication.translate("FacetFilter", text)


# These texts must be fetched at use, not at import. A module is loaded before
# the translator is installed, so a constant here would stay English whatever
# language was chosen.

def empty_label():
    """Shown in place of an empty value."""
    return _tr("(empty)")


def all_label():
    """The row at the top of the drop-down that checks every value."""
    return _tr("(select all)")

# vertical gap between two filter rows
ROW_SPACING = 3

# height of the separator line below the column picker
SEPARATOR_HEIGHT = 1

# space above and below the separator, that is between "Add filter column:" and
# the filters. Adjust this alone to change the gap - heightForRows() accounts
# for it.
HEADER_GAP = 10


class CheckableValueCombo(QComboBox):
    """A drop-down with check boxes that does not close on a click."""

    checkedChanged = pyqtSignal()

    def __init__(self, parent=None):
        super(CheckableValueCombo, self).__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.view().pressed.connect(self._item_pressed)
        self._keep_open = False
        self._checked = set()       # stored values, not displayed texts
        self._labels = {}           # stored value -> displayed text
        self._quiet = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumWidth(90)

    # -- values ------------------------------------------------------------

    def setValues(self, entries):
        """Fill the drop-down.

        `entries` is a list of (stored value, displayed text, count), in the
        order they should appear. Existing check marks are kept.
        """
        # texts that occur more than once get the code appended, to tell them apart
        seen = {}
        for _value, label, _count in entries:
            seen[label] = seen.get(label, 0) + 1

        self._quiet = True
        try:
            model = self.model()
            model.clear()

            # the top row checks every value. To see all but two or three, it
            # is one click here and then two clearings, rather than one click
            # per value you want included
            all_item = QStandardItem(all_label())
            all_item.setData(True, ALL_ROLE)
            all_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            font = all_item.font()
            font.setItalic(True)
            all_item.setFont(font)
            all_item.setToolTip(self.tr(
                "Check every value, then clear the few you do not want to "
                "see. Click again to clear them all."))
            model.appendRow(all_item)

            for value, label, count in entries:
                self._labels[value] = label
                shown = label if label else empty_label()
                if label and seen.get(label, 0) > 1 and value:
                    shown = u"{} [{}]".format(label, value)
                item = QStandardItem(u"{}  ({})".format(shown, count))
                item.setData(value, VALUE_ROLE)
                if label and label != value:
                    item.setToolTip(
                        self.tr("Stored value: {0}").format(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.Checked if value in self._checked else Qt.Unchecked)
                model.appendRow(item)
            self._refresh_all_item()
        finally:
            self._quiet = False
        self.updateGeometry()
        self.update()

    def checkedValues(self):
        """The stored values that are checked."""
        return set(self._checked)

    def setCheckedValues(self, values):
        self._checked = set(values)
        self._apply_states()

    def _listed_values(self):
        """The values in the drop-down right now, excluding the select-all row."""
        values = []
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None or item.data(ALL_ROLE):
                continue
            values.append(item.data(VALUE_ROLE))
        return values

    def _all_item(self):
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is not None and item.data(ALL_ROLE):
                return item
        return None

    def _refresh_all_item(self):
        """Show whether all, some or no values are checked."""
        item = self._all_item()
        if item is None:
            return
        listed = self._listed_values()
        checked = [value for value in listed if value in self._checked]
        if not checked:
            state = Qt.Unchecked
        elif len(checked) == len(listed):
            state = Qt.Checked
        else:
            state = Qt.PartiallyChecked
        item.setCheckState(state)

    def _apply_states(self):
        """Set every check box according to `self._checked`."""
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row)
            if item is None or item.data(ALL_ROLE):
                continue
            item.setCheckState(
                Qt.Checked if item.data(VALUE_ROLE) in self._checked
                else Qt.Unchecked)
        self._refresh_all_item()
        self.update()

    def clearChecked(self):
        self.setCheckedValues(set())

    # -- interaction -------------------------------------------------------

    def _item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item is None:
            return

        if item.data(ALL_ROLE):
            listed = self._listed_values()
            if listed and all(value in self._checked for value in listed):
                self._checked.difference_update(listed)
            else:
                self._checked.update(listed)
            self._apply_states()
            self._keep_open = True
            if not self._quiet:
                self.checkedChanged.emit()
            return

        value = item.data(VALUE_ROLE)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
            self._checked.discard(value)
        else:
            item.setCheckState(Qt.Checked)
            self._checked.add(value)
        self._refresh_all_item()
        self._keep_open = True
        self.update()
        if not self._quiet:
            self.checkedChanged.emit()

    def hidePopup(self):
        """Keep the popup open while values are being checked."""
        if self._keep_open:
            self._keep_open = False
            return
        super(CheckableValueCombo, self).hidePopup()

    # -- display -----------------------------------------------------------

    def _summary(self):
        count = len(self._checked)
        if count == 0:
            return self.tr("all")
        listed = self._listed_values()
        if listed and all(value in self._checked for value in listed):
            return self.tr("all ({0})").format(len(listed))
        if count == 1:
            value = list(self._checked)[0]
            label = self._labels.get(value, value)
            return label if label else empty_label()
        return self.tr("{0} selected").format(count)

    def paintEvent(self, _event):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = self._summary()
        painter.drawComplexControl(QStyle.CC_ComboBox, option)
        painter.drawControl(QStyle.CE_ComboBoxLabel, option)


class FacetWidget(QWidget):
    """One column, its value drop-down and a remove button, on one compact row."""

    changed = pyqtSignal()
    removeRequested = pyqtSignal(object)

    # fixed label width, so the drop-downs line up in the same column
    LABEL_WIDTH = 104

    def __init__(self, column_name, header_label, column_index, parent=None):
        super(FacetWidget, self).__init__(parent)
        self.column_name = column_name
        self.column_index = column_index

        # the row must not stretch: without this the scroll area spreads its
        # surplus height out between the rows
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        height = max(18, self.fontMetrics().height() + 4)
        self.setFixedHeight(height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        label = QLabel(self)
        label.setFixedWidth(self.LABEL_WIDTH)
        label.setText(self._elided(header_label, self.LABEL_WIDTH))
        label.setToolTip(u"{} ({})".format(header_label, column_name)
                         if header_label != column_name else column_name)
        layout.addWidget(label)

        self.combo = CheckableValueCombo(self)
        self.combo.setFixedHeight(height)
        self.combo.checkedChanged.connect(self.changed)
        layout.addWidget(self.combo, 1)

        self.btnRemove = QToolButton(self)
        self.btnRemove.setText(u"✕")
        self.btnRemove.setAutoRaise(True)
        self.btnRemove.setFixedSize(height, height)
        self.btnRemove.setToolTip(self.tr("Remove this filter"))
        self.btnRemove.clicked.connect(lambda: self.removeRequested.emit(self))
        layout.addWidget(self.btnRemove)

    def _elided(self, text, width):
        """Shorten a long column header that would not otherwise fit."""
        metrics = self.fontMetrics()
        return metrics.elidedText(u"{}:".format(text), Qt.ElideRight, width - 2)

    def checkedValues(self):
        return self.combo.checkedValues()

    def setValues(self, entries):
        self.combo.setValues(entries)

    def clearChecked(self):
        self.combo.clearChecked()


class FacetBar(QWidget):
    """Manages the set of active column filters."""

    filtersChanged = pyqtSignal()   # a value choice changed, rows must be refiltered
    columnsChanged = pyqtSignal()   # a column filter was added or removed

    def __init__(self, parent=None):
        super(FacetBar, self).__init__(parent)
        self._facets = []
        self._columns = []          # list of (field name, column header)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # the gaps are set explicitly below, so the height calculation in
        # heightForRows() matches exactly what the layout does
        outer.setSpacing(0)
        self._outer = outer

        # the top row goes in its own widget, so its height can be measured
        # precisely when the filter area is resized
        self._header = QWidget(self)
        top = QHBoxLayout(self._header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(3)
        top.addWidget(QLabel(self.tr("Add filter column:"), self._header))
        self.cboColumn = QComboBox(self._header)
        self.cboColumn.setToolTip(self.tr("Pick a column and click Add"))
        top.addWidget(self.cboColumn, 1)
        self.btnAdd = QToolButton(self._header)
        self.btnAdd.setText(self.tr("Add"))
        self.btnAdd.clicked.connect(self._add_current)
        top.addWidget(self.btnAdd)
        self.btnReset = QToolButton(self._header)
        self.btnReset.setText(self.tr("Reset"))
        self.btnReset.setToolTip(self.tr("Remove all column filters"))
        self.btnReset.clicked.connect(self.reset)
        top.addWidget(self.btnReset)
        outer.addWidget(self._header)
        outer.addSpacing(HEADER_GAP)

        # separator between the column picker and the active filters
        self._separator = QFrame(self)
        self._separator.setFrameShape(QFrame.HLine)
        self._separator.setFrameShadow(QFrame.Sunken)
        self._separator.setFixedHeight(SEPARATOR_HEIGHT)
        outer.addWidget(self._separator)
        outer.addSpacing(HEADER_GAP)

        self._container = QVBoxLayout()
        self._container.setContentsMargins(0, 0, 0, 0)
        self._container.setSpacing(ROW_SPACING)
        outer.addLayout(self._container)

        # Without this the scroll area spreads its surplus height out between
        # the rows, leaving large gaps. The stretch gathers the space at the
        # bottom instead.
        outer.addStretch(1)

    # -- height calculation ------------------------------------------------

    def rowHeight(self):
        """The height of one filter row. Same formula as in FacetWidget."""
        return max(18, self.fontMetrics().height() + 4)

    def heightForRows(self, rows):
        """The height the filter area needs to show `rows` rows in full.

        Computed from the heights of the individual parts rather than
        sizeHint(). The call happens right after a row is added, and at that
        point the layout has not yet updated its cached sizeHint - which was
        why the area showed one row fewer than there were.
        """
        height = self._header.sizeHint().height()
        height += HEADER_GAP + SEPARATOR_HEIGHT + HEADER_GAP
        if rows > 0:
            height += rows * self.rowHeight()
            height += (rows - 1) * ROW_SPACING
        return height + 2                        # a little slack, so nothing is clipped

    # -- setup -------------------------------------------------------------

    def setColumns(self, columns):
        """`columns` is a list of (field name, column header) in table order.

        The header is the alias of the field where one is set.
        """
        self.reset(emit=False)
        self._columns = list(columns)
        self.cboColumn.clear()
        for name, header in self._columns:
            self.cboColumn.addItem(header, name)
            if header != name:
                index = self.cboColumn.count() - 1
                self.cboColumn.setItemData(index, name, Qt.ToolTipRole)
        self.setEnabled(bool(self._columns))

    def reset(self, emit=True):
        for facet in list(self._facets):
            self._remove(facet, emit=False)
        if emit:
            self.filtersChanged.emit()
            self.columnsChanged.emit()

    def columnNames(self):
        """Field names of the active column filters, in the order they appear."""
        return [facet.column_name for facet in self._facets]

    def restoreColumns(self, names):
        """Restore column filters without any value choices.

        Unknown field names are skipped, so a column remembered from another
        table does not cause an error. No signals are emitted along the way -
        the caller updates the value lists and counts afterwards.
        """
        available = {name: position
                     for position, (name, _header) in enumerate(self._columns)}
        for name in names:
            if name not in available or any(
                    f.column_name == name for f in self._facets):
                continue
            self._create(name, available[name])

    # -- filters -----------------------------------------------------------

    def activeFilters(self):
        """Returns {column index: set(stored values)} for filters with a choice."""
        active = {}
        for facet in self._facets:
            values = facet.checkedValues()
            if values:
                active[facet.column_index] = values
        return active

    def facets(self):
        return list(self._facets)

    def _create(self, name, column_index):
        """Create a column filter without emitting signals."""
        header = name
        for candidate, candidate_header in self._columns:
            if candidate == name:
                header = candidate_header
                break
        facet = FacetWidget(name, header, column_index, self)
        facet.changed.connect(self.filtersChanged)
        facet.removeRequested.connect(self._remove)
        self._facets.append(facet)
        self._container.addWidget(facet)
        return facet

    def _add_current(self):
        index = self.cboColumn.currentIndex()
        if index < 0:
            return
        name = self.cboColumn.itemData(index)
        if any(f.column_name == name for f in self._facets):
            return
        self._create(name, index)
        self.columnsChanged.emit()
        self.filtersChanged.emit()

    def _remove(self, facet, emit=True):
        if facet not in self._facets:
            return
        had_values = bool(facet.checkedValues())
        self._facets.remove(facet)
        self._container.removeWidget(facet)
        facet.setParent(None)
        facet.deleteLater()
        if emit:
            self.columnsChanged.emit()
            if had_values:
                self.filtersChanged.emit()
