# -*- coding: utf-8 -*-
"""
search_panel.py
---------------
The search panel: free-text search and column filters on a table without
geometry, where the selected rows select the related polygons in one or more
map layers.

Three filters act at once and combine with AND:

    filter expression   from the setup, applied when the table is loaded
    free text           every word must appear in one of the shown columns
    column filters      OR within a column, AND between columns

Rows can be selected one at a time, or every filtered row at once with the
button below the table.

A configuration has a list of target layers, not one. Where the same table
points at several layers - because the geometries are split across two layers,
say, with a given key only in one of them - the key is looked up in all of them
and the matching layers get the selection.
"""

from qgis.PyQt.QtCore import (
    Qt, QSortFilterProxyModel, QTimer, pyqtSignal, QCoreApplication,
)
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QGuiApplication, QCursor
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit, QTableView,
    QCheckBox, QLabel, QPushButton, QAbstractItemView, QHeaderView,
    QScrollArea, QMessageBox, QFrame,
)
from qgis.core import (
    QgsProject, QgsFeatureRequest, QgsWkbTypes, QgsRectangle,
    QgsCoordinateTransform, QgsExpression, Qgis,
)
from qgis.gui import QgsDockWidget, QgsCollapsibleGroupBox, QgsFieldExpressionWidget

from ..core.project_config import (
    load_configs, configs_from_relations, resolve_layer, validate_config,
    normalize_key, no_geometry_flag, log, save_configs,
    load_facet_columns, save_facet_columns, is_alive,
)
from ..core.key_index import KeyIndex
from .facet_filter import FacetBar
from ..core.value_format import ValueFormatter, raw_text

def _tr(text):
    """Translate a string used before self.tr() is available."""
    return QCoreApplication.translate("SearchPanel", text)


VALUE_ROLE = Qt.UserRole + 1    # the key value of the row, always raw
RAW_ROLE = Qt.UserRole + 2      # the stored cell value, what filters match on
SORT_ROLE = Qt.UserRole + 3     # sort value: numbers as numbers, else text
FID_ROLE = Qt.UserRole + 4      # the feature id of the row in the table layer

# Above this many keys the user is asked before all filtered rows are selected.
SELECT_WARN_THRESHOLD = 500

# How many filter rows can be shown at once. Above that the filter area gets
# its own scroll bar, so the table is not squeezed away.
FACET_VISIBLE_ROWS = 5

# gap between the search box and the table
FACET_TABLE_GAP = 6

# luft over og under skillelinjen mellem forfilter og kolonnefiltre
SECTION_GAP = 4


def _sort_key(value):
    """Sort numbers as numbers and text alphabetically, empty values last."""
    if value is None or value == u"":
        return (2, 0.0, u"")
    try:
        return (0, float(value), u"")
    except (TypeError, ValueError):
        return (1, 0.0, value.lower())


class RowFilterProxy(QSortFilterProxyModel):
    """A free-text filter combined with per-column value filters."""

    def __init__(self, parent=None):
        super(RowFilterProxy, self).__init__(parent)
        self._terms = []
        self._facets = {}       # kolonneindeks -> set(tilladte værdier)

    # -- setting up the filters --------------------------------------------

    def setSearchText(self, text):
        self._terms = [t.lower() for t in (text or u"").split() if t]
        self.invalidateFilter()

    def setFacets(self, facets):
        self._facets = dict(facets or {})
        self.invalidateFilter()

    # -- filtrering --------------------------------------------------------

    def _index(self, row, column):
        return self.sourceModel().index(row, column)

    def _display(self, row, column):
        """The displayed text, that is the value map text if the field has one."""
        return self._index(row, column).data(Qt.DisplayRole) or u""

    def _raw(self, row, column):
        """The stored value. Filters match on this, not on the displayed text,
        så to koder med samme tekst ikke smelter sammen."""
        value = self._index(row, column).data(RAW_ROLE)
        return u"" if value is None else value

    def _passes(self, row, skip_column=None):
        for column, allowed in self._facets.items():
            if column == skip_column:
                continue
            if self._raw(row, column) not in allowed:
                return False
        if self._terms:
            model = self.sourceModel()
            parts = []
            for column in range(model.columnCount()):
                shown = self._display(row, column)
                stored = self._raw(row, column)
                parts.append(shown)
                if stored and stored != shown:
                    # so both "Grazing" and "graesning" find the same rows
                    parts.append(stored)
            haystack = u" ".join(parts).lower()
            if not all(term in haystack for term in self._terms):
                return False
        return True

    def filterAcceptsRow(self, row, _parent):
        return self._passes(row)

    # -- cascade -----------------------------------------------------------

    def valueCounts(self, column, skip_column=None):
        """Values in `column` among the rows passing the other filters.

        Returns a list of (stored value, displayed text, count), sorted by the
        displayed text. Called with skip_column = column, so a column's own
        drop-down does not narrow itself to only the values already chosen.
        """
        counts = {}
        labels = {}
        model = self.sourceModel()
        for row in range(model.rowCount()):
            if not self._passes(row, skip_column=skip_column):
                continue
            stored = self._raw(row, column)
            counts[stored] = counts.get(stored, 0) + 1
            if stored not in labels:
                labels[stored] = self._display(row, column)
        entries = [(stored, labels[stored], count)
                   for stored, count in counts.items()]
        return sorted(entries, key=lambda item: _sort_key(item[1]))


class SearchPanel(QgsDockWidget):
    """Dock panel: search and filter the table, select the related polygons."""

    selectionApplied = pyqtSignal(int)

    def __init__(self, iface, parent=None):
        super(SearchPanel, self).__init__(
            _tr("Search Related Features"), parent)
        self.setObjectName("SearchRelatedFeaturesPanel")
        self.iface = iface
        self.configs = []
        self.index = KeyIndex()
        self._loading = False
        self._syncing = False
        self._restoring = False
        self._watched = []
        self._columns = []

        self._build_ui()

    # -- opbygning ---------------------------------------------------------

    def _build_ui(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.cboConfig = QComboBox(container)
        self.cboConfig.setToolTip(self.tr("Pick the table to search in"))
        self.cboConfig.currentIndexChanged.connect(self._config_changed)
        layout.addWidget(self.cboConfig)

        # The order follows the way the rows are cut down: the pre-filter
        # decides what is fetched at all, and the column filters and free text
        # then work on what was fetched.

        # pre-filter: cuts rows away already when the table is fetched, unlike
        # the other filters which work on the loaded rows
        self.grpFilter = QgsCollapsibleGroupBox(
            self.tr("Pre-filter"), container)
        self.grpFilter.setObjectName("SearchRelatedFeaturesPrefilter")
        self.grpFilter.setCollapsed(True)
        filter_layout = QVBoxLayout(self.grpFilter)
        filter_layout.setContentsMargins(6, 2, 6, 6)
        filter_layout.setSpacing(3)

        self.expFilter = QgsFieldExpressionWidget(self.grpFilter)
        self.expFilter.setToolTip(
            self.tr("Expression that limits which rows are fetched, for "
                    "example \"Status\" < 100 or \"Completed\" IS NULL"))
        filter_layout.addWidget(self.expFilter)

        filter_buttons = QHBoxLayout()
        filter_buttons.setSpacing(4)
        self.btnApplyFilter = QPushButton(self.tr("Apply"), self.grpFilter)
        self.btnApplyFilter.setToolTip(
            self.tr("Fetch the table again with this expression"))
        self.btnApplyFilter.clicked.connect(self._apply_prefilter)
        filter_buttons.addWidget(self.btnApplyFilter)
        self.btnClearFilter = QPushButton(self.tr("Clear"), self.grpFilter)
        self.btnClearFilter.setToolTip(self.tr("Fetch all rows again"))
        self.btnClearFilter.clicked.connect(self._clear_prefilter)
        filter_buttons.addWidget(self.btnClearFilter)
        filter_buttons.addStretch()
        self.btnSaveFilter = QPushButton(
            self.tr("Save in the project"), self.grpFilter)
        self.btnSaveFilter.setToolTip(
            self.tr("Make the expression the default for this "
                    "configuration. Remember to save the project "
                    "afterwards."))
        self.btnSaveFilter.clicked.connect(self._save_prefilter)
        filter_buttons.addWidget(self.btnSaveFilter)
        filter_layout.addLayout(filter_buttons)
        layout.addWidget(self.grpFilter)

        # skillelinje mellem forfilteret og kolonnefiltrene
        layout.addSpacing(SECTION_GAP)
        self.sepPrefilter = QFrame(container)
        self.sepPrefilter.setFrameShape(QFrame.HLine)
        self.sepPrefilter.setFrameShadow(QFrame.Sunken)
        self.sepPrefilter.setFixedHeight(2)
        layout.addWidget(self.sepPrefilter)
        layout.addSpacing(SECTION_GAP)

        # column filters in a scroll area, so the panel does not grow unchecked
        self.facetBar = FacetBar(container)
        self.facetBar.filtersChanged.connect(self._filters_changed)
        self.facetBar.columnsChanged.connect(self._facet_columns_changed)
        self.facetScroll = QScrollArea(container)
        self.facetScroll.setWidget(self.facetBar)
        self.facetScroll.setWidgetResizable(True)
        self.facetScroll.setFrameShape(QFrame.NoFrame)
        self.facetScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.facetScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        layout.addWidget(self.facetScroll)
        self._resize_facet_area()

        # free text last: it narrows what the column filters have left
        self.txtSearch = QLineEdit(container)
        self.txtSearch.setPlaceholderText(self.tr("Free-text search…"))
        self.txtSearch.setClearButtonEnabled(True)
        self.txtSearch.setToolTip(
            self.tr("Several search words are combined with AND and searched "
                    "in all shown columns"))
        layout.addWidget(self.txtSearch)
        layout.addSpacing(FACET_TABLE_GAP)

        self.model = QStandardItemModel(self)
        self.proxy = RowFilterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)

        # a delay, so filtering does not run on every keystroke
        self._filterTimer = QTimer(self)
        self._filterTimer.setSingleShot(True)
        self._filterTimer.setInterval(200)
        self._filterTimer.timeout.connect(self._apply_text_filter)
        self.txtSearch.textChanged.connect(lambda _t: self._filterTimer.start())

        self.table = QTableView(container)
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.selectionModel().selectionChanged.connect(self._rows_changed)
        layout.addWidget(self.table)

        self.lblCount = QLabel(u"", container)
        layout.addWidget(self.lblCount)

        self.btnSelectFiltered = QPushButton(
            self.tr("Select filtered rows"), container)
        self.btnSelectFiltered.setToolTip(
            self.tr("Select the polygons for every row shown with the "
                    "current filters"))
        self.btnSelectFiltered.clicked.connect(self._select_filtered)
        layout.addWidget(self.btnSelectFiltered)

        options = QHBoxLayout()
        self.chkZoom = QCheckBox(self.tr("Zoom"), container)
        self.chkZoom.setChecked(True)
        self.chkActivate = QCheckBox(self.tr("Activate layer"), container)
        self.chkFollowMap = QCheckBox(
            self.tr("Follow map selection"), container)
        self.chkFollowMap.setToolTip(
            self.tr("Select rows in the table when polygons are selected in "
                    "the map"))
        self.chkFollowMap.toggled.connect(self._follow_map_toggled)
        options.addWidget(self.chkZoom)
        options.addWidget(self.chkActivate)
        options.addWidget(self.chkFollowMap)
        options.addStretch()
        self.btnClear = QPushButton(self.tr("Clear"), container)
        self.btnClear.setToolTip(
            self.tr("Clear search, filters and selections"))
        self.btnClear.clicked.connect(self.clear)
        options.addWidget(self.btnClear)
        layout.addLayout(options)

        self.lblStatus = QLabel(u"", container)
        self.lblStatus.setWordWrap(True)
        layout.addWidget(self.lblStatus)

        self.setWidget(container)

    # -- livscyklus --------------------------------------------------------

    def reload(self):
        """Reload the setup from the project. Connected to iface.projectRead."""
        self._disconnect_map_sync()
        self.index.clear()
        self._loading = True
        self.cboConfig.clear()
        self.model.clear()
        self.facetBar.reset(emit=False)
        self.proxy.setFacets({})

        configs = load_configs()
        derived = False
        if not configs:
            # nothing stored yet: fall back on the relations of the project
            configs = configs_from_relations()
            derived = True

        self.configs = []
        for cfg in configs:
            usable, problems = validate_config(cfg)
            for problem in problems:
                log(u"{}: {}".format(cfg.get("name", "?"), problem), Qgis.Warning)
            if usable:
                self.configs.append(cfg)

        for cfg in self.configs:
            self.cboConfig.addItem(cfg.get("name") or u"?")
        self._loading = False

        if self.configs:
            self.cboConfig.setCurrentIndex(0)
            self._populate()
            if self.chkFollowMap.isChecked():
                self._connect_map_sync()
            if derived:
                self.lblStatus.setText(
                    self.tr("Setup derived from the project relations - "
                            "save it with the settings button."))
        else:
            self.lblStatus.setText(
                self.tr("No usable setup or relation found in the project."))
            self._update_counts()

    def teardown(self):
        """Kaldes fra plugin'ets unload()."""
        self._disconnect_map_sync()
        self.index.clear()

    # -- choice of configuration -------------------------------------------

    def current_config(self):
        i = self.cboConfig.currentIndex()
        return self.configs[i] if 0 <= i < len(self.configs) else None

    def _config_changed(self, _index):
        if self._loading:
            return
        self.txtSearch.clear()
        self.facetBar.reset(emit=False)
        self.proxy.setFacets({})
        self._populate()
        if self.chkFollowMap.isChecked():
            self._connect_map_sync()

    # -- loading the table -------------------------------------------------

    def _populate(self):
        self.model.clear()
        cfg = self.current_config()
        if cfg is None:
            self._update_counts()
            return

        table = resolve_layer(cfg["table"])
        fields = table.fields()
        key = cfg["table_key"]

        names = [n for n in (cfg.get("search_fields") or [])
                 if fields.lookupField(n) >= 0]
        if not names:
            names = [f.name() for f in fields]
        if key not in names:
            names.append(key)

        headers = [fields.field(fields.lookupField(n)).displayName()
                   for n in names]
        self.model.setHorizontalHeaderLabels(headers)
        self._columns = list(zip(names, headers))

        request = QgsFeatureRequest()
        request.setSubsetOfAttributes(names, fields)
        if table.geometryType() != QgsWkbTypes.NullGeometry:
            request.setFlags(no_geometry_flag())

        expression = (cfg.get("filter_expression") or u"").strip()
        if expression:
            if QgsExpression(expression).hasParserError():
                log(u"Invalid filter expression on '{}': {}".format(
                    cfg.get("name"), expression), Qgis.Warning)
            else:
                request.setFilterExpression(expression)

        formatter = ValueFormatter(table)
        indexes = [fields.lookupField(n) for n in names]

        QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            for feature in table.getFeatures(request):
                key_value = normalize_key(feature[key])
                row = []
                for name, field_index in zip(names, indexes):
                    value = feature[name]
                    stored = raw_text(value)
                    label = formatter.label(field_index, value)
                    item = QStandardItem(label)
                    item.setData(key_value, VALUE_ROLE)
                    item.setData(feature.id(), FID_ROLE)
                    item.setData(stored, RAW_ROLE)
                    item.setData(formatter.sort_value(value, label), SORT_ROLE)
                    if label != stored:
                        item.setToolTip(
                            self.tr("Stored value: {0}").format(stored))
                    row.append(item)
                self.model.appendRow(row)
        finally:
            QGuiApplication.restoreOverrideCursor()

        self.table.resizeColumnsToContents()
        self.facetBar.setColumns(self._columns)

        # restore the column filters last in use, without any value choices
        self._restoring = True
        try:
            self.expFilter.setLayer(table)
            self.expFilter.setExpression(expression)
            self.facetBar.restoreColumns(load_facet_columns(cfg))
        finally:
            self._restoring = False
        self._resize_facet_area()

        self.proxy.setFacets({})
        self._refresh_facet_values()
        self._update_prefilter_state()
        self.lblStatus.setText(self.tr("Table: {0}").format(table.name()))
        self._update_counts()

    # -- forfilter ---------------------------------------------------------

    def _update_prefilter_state(self):
        """Vis i gruppetitlen om der er et forfilter i brug."""
        expression = (self.expFilter.expression() or u"").strip()
        self.grpFilter.setTitle(
            self.tr("Pre-filter (active)") if expression
            else self.tr("Pre-filter"))

    def _apply_prefilter(self):
        cfg = self.current_config()
        if cfg is None:
            return
        expression = (self.expFilter.expression() or u"").strip()
        if expression and not self.expFilter.isValidExpression():
            self.lblStatus.setText(
                self.tr("The expression cannot be parsed: {0}").format(
                    self.expFilter.parserErrorString()))
            return
        cfg["filter_expression"] = expression
        self._populate()

    def _clear_prefilter(self):
        cfg = self.current_config()
        if cfg is None:
            return
        self.expFilter.setExpression(u"")
        cfg["filter_expression"] = u""
        self._populate()

    def _save_prefilter(self):
        """Make the current expression the default for the configuration."""
        cfg = self.current_config()
        if cfg is None:
            return
        self._apply_prefilter()
        save_configs(self.configs)
        self.lblStatus.setText(
            self.tr("The pre-filter is saved in the setup. Remember to save "
                    "the project."))

    # -- filtre ------------------------------------------------------------

    def _apply_text_filter(self):
        self.proxy.setSearchText(self.txtSearch.text())
        self._refresh_facet_values()
        self._update_counts()

    def _filters_changed(self):
        self.proxy.setFacets(self.facetBar.activeFilters())
        self._refresh_facet_values()
        self._update_counts()

    def _facet_columns_changed(self):
        """Remember which columns are filtered on, but not the value choices."""
        self._resize_facet_area()
        if self._restoring:
            return
        cfg = self.current_config()
        if cfg is None:
            return
        save_facet_columns(cfg, self.facetBar.columnNames())
        self._refresh_facet_values()
        self._update_counts()

    def _resize_facet_area(self):
        """Give the filter area room for the rows, up to FACET_VISIBLE_ROWS.

        The height is computed from the parts' own measurements rather than
        sizeHint(): the call happens immediately after a row is added or
        removed, and at that point the cached sizeHint of the layout has not
        been updated.
        """
        rows = min(len(self.facetBar.facets()), FACET_VISIBLE_ROWS)
        height = self.facetBar.heightForRows(rows)
        self.facetScroll.setMinimumHeight(height)
        self.facetScroll.setMaximumHeight(height)

    def _refresh_facet_values(self):
        """Update each drop-down with the values that are still possible."""
        for facet in self.facetBar.facets():
            counted = self.proxy.valueCounts(
                facet.column_index, skip_column=facet.column_index)
            facet.setValues(counted)

    def _update_counts(self):
        visible = self.proxy.rowCount()
        total = self.model.rowCount()
        self.lblCount.setText(
            self.tr("{0} of {1} rows shown").format(visible, total))
        self.btnSelectFiltered.setText(
            self.tr("Select filtered rows ({0})").format(visible))
        self.btnSelectFiltered.setEnabled(visible > 0)

    # -- panel -> table layer ----------------------------------------------

    def _selected_row_fids(self):
        """Feature ids of the rows selected in the panel."""
        fids = []
        seen = set()
        for index in self.table.selectionModel().selectedRows():
            fid = index.data(FID_ROLE)
            if fid is not None and fid not in seen:
                seen.add(fid)
                fids.append(fid)
        return fids

    def _select_in_table(self, fids, cfg=None):
        """Select the same rows in the table layer itself.

        Without this the selection in the panel is merely visual. The QGIS
        attribute table, "Save Selected Features As" and expressions using
        `is_selected()` all work on the layer selection, not the panel one, so
        the rows could not be exported.

        `_syncing` is set for the duration: if the table layer is also a target
        layer - when searching a polygon layer, say - the selectionChanged of
        the layer would otherwise call back and overwrite the selection again.
        """
        cfg = cfg or self.current_config()
        if cfg is None:
            return
        table = resolve_layer(cfg["table"])
        if table is None:
            return
        previous = self._syncing
        self._syncing = True
        try:
            if fids:
                table.selectByIds(fids)
            else:
                table.removeSelection()
        finally:
            self._syncing = previous

    # -- table -> map ------------------------------------------------------

    def _rows_changed(self, *_args):
        if self._syncing:
            return
        cfg = self.current_config()
        if cfg is None:
            return
        values = []
        for index in self.table.selectionModel().selectedRows():
            value = index.data(VALUE_ROLE)
            if value is not None and value not in values:
                values.append(value)
        self._select_in_table(self._selected_row_fids(), cfg)
        self._select_in_targets(cfg, values)

    def _select_filtered(self):
        """Select the polygons for every row shown right now."""
        cfg = self.current_config()
        if cfg is None:
            return

        values = []
        seen = set()
        fids = []
        seen_fids = set()
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            value = index.data(VALUE_ROLE)
            if value is not None and value not in seen:
                seen.add(value)
                values.append(value)
            fid = index.data(FID_ROLE)
            if fid is not None and fid not in seen_fids:
                seen_fids.add(fid)
                fids.append(fid)

        if not values:
            self.lblStatus.setText(self.tr("No rows to select."))
            return

        if len(values) > SELECT_WARN_THRESHOLD:
            answer = QMessageBox.question(
                self, self.tr("Select many polygons"),
                self.tr("The filters give {0} distinct keys.\n\nSelecting that "
                        "many polygons may take a moment. "
                        "Continue?").format(len(values)),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return

        # select every shown row in the panel, so it is clear what was chosen.
        # The proxy only holds the rows the filters let through, so selectAll()
        # hits exactly those
        self._syncing = True
        try:
            self.table.selectAll()
        finally:
            self._syncing = False

        # every shown row is selected in the table layer, so the filtered set
        # can be exported straight from the layer
        self._select_in_table(fids, cfg)
        self._select_in_targets(cfg, values)

    def _select_in_targets(self, cfg, values):
        hits = []
        total = 0

        self._syncing = True
        try:
            for target in cfg["targets"]:
                layer = resolve_layer(target["layer"])
                if layer is None:
                    continue
                if not values:
                    layer.removeSelection()
                    continue
                fids = self.index.lookup(layer, target["key"], values)
                layer.selectByIds(fids)
                if fids:
                    hits.append((layer, fids))
                    total += len(fids)
        finally:
            self._syncing = False

        if not values:
            self.lblStatus.setText(u"")
            return

        if hits and self.chkActivate.isChecked():
            self.iface.setActiveLayer(hits[0][0])
        if hits and self.chkZoom.isChecked():
            self._zoom_to(hits)
        elif hits:
            for layer, fids in hits:
                self.iface.mapCanvas().flashFeatureIds(layer, fids)

        if total:
            parts = [self.tr("{0} in {1}").format(len(f), l.name())
                     for l, f in hits]
            self.lblStatus.setText(self.tr("Selected: ") + u", ".join(parts))
        else:
            self.lblStatus.setText(
                self.tr("No polygon found for {0} selected key(s) - check "
                        "whether the rows are orphaned.").format(len(values)))
        self.selectionApplied.emit(total)

    def _zoom_to(self, hits):
        canvas = self.iface.mapCanvas()
        if len(hits) == 1:
            canvas.zoomToSelected(hits[0][0])
            return

        context = QgsProject.instance().transformContext()
        destination = canvas.mapSettings().destinationCrs()
        extent = QgsRectangle()
        extent.setMinimal()
        for layer, _fids in hits:
            bbox = layer.boundingBoxOfSelected()
            if bbox.isNull():
                continue
            if layer.crs() != destination:
                bbox = QgsCoordinateTransform(
                    layer.crs(), destination, context).transformBoundingBox(bbox)
            extent.combineExtentWith(bbox)
        if not extent.isNull():
            extent.scale(1.1)
            canvas.setExtent(extent)
            canvas.refresh()

    # -- kort -> tabel -----------------------------------------------------

    def _follow_map_toggled(self, enabled):
        if enabled:
            self._connect_map_sync()
        else:
            self._disconnect_map_sync()

    def _connect_map_sync(self):
        self._disconnect_map_sync()
        cfg = self.current_config()
        if cfg is None:
            return
        for target in cfg["targets"]:
            layer = resolve_layer(target["layer"])
            if layer is None:
                continue
            layer.selectionChanged.connect(self._map_selection_changed)
            self._watched.append(layer)

    def _disconnect_map_sync(self):
        """Kobl fra igen. Lag der er slettet i C++ springes over - Qt har selv
        koblet dem fra, og de må ikke røres."""
        for layer in self._watched:
            if not is_alive(layer):
                continue
            try:
                layer.selectionChanged.disconnect(self._map_selection_changed)
            except (TypeError, RuntimeError):
                pass
        self._watched = []

    def _map_selection_changed(self, *_args):
        if self._syncing:
            return
        cfg = self.current_config()
        if cfg is None:
            return

        wanted = set()
        for target in cfg["targets"]:
            layer = resolve_layer(target["layer"])
            if layer is None or layer.selectedFeatureCount() == 0:
                continue
            field_index = layer.fields().lookupField(target["key"])
            if field_index < 0:
                continue
            for feature in layer.getSelectedFeatures():
                key = normalize_key(feature[field_index])
                if key is not None:
                    wanted.add(key)

        self._syncing = True
        try:
            selection_model = self.table.selectionModel()
            selection_model.clearSelection()
            if not wanted:
                self._select_in_table([], cfg)
                self.lblStatus.setText(u"")
                return
            first = None
            for row in range(self.proxy.rowCount()):
                index = self.proxy.index(row, 0)
                if index.data(VALUE_ROLE) in wanted:
                    selection_model.select(
                        index, selection_model.Select | selection_model.Rows)
                    if first is None:
                        first = index
            if first is not None:
                self.table.scrollTo(first, QAbstractItemView.PositionAtCenter)
            self._select_in_table(self._selected_row_fids(), cfg)
            matched = len(selection_model.selectedRows())
            if matched:
                self.lblStatus.setText(
                    self.tr("{0} row(s) match the map selection").format(
                        matched))
            else:
                self.lblStatus.setText(
                    self.tr("The map selection matches none of the shown "
                            "rows - the filters may be hiding them."))
        finally:
            self._syncing = False

    # -- other -------------------------------------------------------------

    def clear(self):
        """Clear the search box, value choices, row selection and map selection.

        The column filters stay in place with their value choices cleared, so
        the same columns need not be added again after every search.
        """
        self.txtSearch.clear()
        for facet in self.facetBar.facets():
            facet.clearChecked()
        self.proxy.setFacets({})
        self.proxy.setSearchText(u"")
        self._refresh_facet_values()
        self._syncing = True
        try:
            self.table.clearSelection()
        finally:
            self._syncing = False

        cfg = self.current_config()
        if cfg:
            self._select_in_table([], cfg)
            for target in cfg["targets"]:
                layer = resolve_layer(target["layer"])
                if layer is not None:
                    layer.removeSelection()
        self.lblStatus.setText(u"")
        self._update_counts()
