# -*- coding: utf-8 -*-
"""
config_dialog.py
----------------
The settings dialog. Here you define which tables can be searched, which field
is linked on, which columns are shown, and which polygon layers get selected.

The setup is written to the project, so the project has to be saved
(Project > Save) for it to end up in the .qgz file.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QLabel, QGroupBox, QCheckBox,
    QDialogButtonBox, QSplitter, QWidget, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
)
from qgis.core import QgsProject, QgsMapLayerProxyModel, QgsWkbTypes
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox, QgsFieldExpressionWidget

from ..core.project_config import (
    load_configs, save_configs, configs_from_relations, resolve_layer,
    validate_config,
)


class ConfigDialog(QDialog):
    """Edit the plugin setup for the current project."""

    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent)
        self.setWindowTitle(self.tr("Search Related Features - settings"))
        self.resize(820, 560)

        self.configs = load_configs()
        self._current_row = -1
        self._loading = False

        self._build_ui()
        self._refresh_list()
        if self.configs:
            self.lstConfigs.setCurrentRow(0)
        else:
            self._set_form_enabled(False)

    # -- construction ------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal, self)

        # left-hand side: the list of configurations
        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel(self.tr("Configurations"), left))

        self.lstConfigs = QListWidget(left)
        self.lstConfigs.currentRowChanged.connect(self._row_changed)
        left_layout.addWidget(self.lstConfigs)

        self.btnFromRelations = QPushButton(
            self.tr("Derive from project relations"), left)
        self.btnFromRelations.setToolTip(
            self.tr("Create one configuration per table with relations, with "
                    "all target layers of the relation and all columns of the "
                    "table"))
        self.btnFromRelations.clicked.connect(self._from_relations)
        left_layout.addWidget(self.btnFromRelations)

        buttons = QHBoxLayout()
        self.btnAdd = QPushButton(self.tr("New"), left)
        self.btnAdd.clicked.connect(self._add)
        self.btnRemove = QPushButton(self.tr("Remove"), left)
        self.btnRemove.clicked.connect(self._remove)
        buttons.addWidget(self.btnAdd)
        buttons.addWidget(self.btnRemove)
        left_layout.addLayout(buttons)
        splitter.addWidget(left)

        # right-hand side: the form
        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self.txtName = QLineEdit(right)
        self.txtName.textChanged.connect(self._name_changed)
        form.addRow(self.tr("Name:"), self.txtName)

        self.cboTable = QgsMapLayerComboBox(right)
        self.cboTable.setFilters(QgsMapLayerProxyModel.NoGeometry)
        self.cboTable.layerChanged.connect(self._table_changed)
        form.addRow(self.tr("Table:"), self.cboTable)

        self.chkAllVector = QCheckBox(
            self.tr("Also show layers with geometry"), right)
        self.chkAllVector.toggled.connect(self._all_vector_toggled)
        form.addRow(u"", self.chkAllVector)

        self.cboKey = QgsFieldComboBox(right)
        self.cboKey.fieldChanged.connect(self._key_changed)
        form.addRow(self.tr("Key field:"), self.cboKey)

        self.expFilter = QgsFieldExpressionWidget(right)
        self.expFilter.setToolTip(
            self.tr("Optional. Limit which rows are fetched, for example "
                    "\"Status\" < 100 or \"Completed\" IS NULL"))
        form.addRow(self.tr("Filter:"), self.expFilter)
        right_layout.addLayout(form)

        columns_box = QGroupBox(
            self.tr("Columns shown and searched"), right)
        columns_layout = QVBoxLayout(columns_box)
        self.lstFields = QListWidget(columns_box)
        self.lstFields.setToolTip(
            self.tr("The key field is always included, even when it is not "
                    "checked here"))
        columns_layout.addWidget(self.lstFields)
        right_layout.addWidget(columns_box)

        targets_box = QGroupBox(self.tr("Target layers to select in"), right)
        targets_layout = QVBoxLayout(targets_box)
        self.lblTargetHint = QLabel(u"", targets_box)
        self.lblTargetHint.setWordWrap(True)
        targets_layout.addWidget(self.lblTargetHint)
        self.tblTargets = QTableWidget(0, 2, targets_box)
        self.tblTargets.setHorizontalHeaderLabels(
            [self.tr("Layer"), self.tr("Key field in the layer")])
        self.tblTargets.verticalHeader().setVisible(False)
        self.tblTargets.setSelectionMode(QAbstractItemView.NoSelection)
        self.tblTargets.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.tblTargets.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        targets_layout.addWidget(self.tblTargets)
        right_layout.addWidget(targets_box)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter)

        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        outer.addWidget(self.buttonBox)

        self.lblNote = QLabel(
            self.tr("The setup is stored in the project. Remember to save "
                    "the project afterwards, so it travels with the .qgz "
                    "file."), self)
        self.lblNote.setWordWrap(True)
        outer.addWidget(self.lblNote)

    def _set_form_enabled(self, enabled):
        for widget in (self.txtName, self.cboTable, self.chkAllVector,
                       self.cboKey, self.expFilter, self.lstFields,
                       self.tblTargets):
            widget.setEnabled(enabled)

    # -- list handling -----------------------------------------------------

    def _refresh_list(self):
        self._loading = True
        self.lstConfigs.clear()
        for cfg in self.configs:
            self.lstConfigs.addItem(cfg.get("name") or self.tr("(unnamed)"))
        self._loading = False

    def _row_changed(self, row):
        if self._loading:
            return
        if 0 <= self._current_row < len(self.configs):
            self._store_form(self.configs[self._current_row])
        self._current_row = row
        if 0 <= row < len(self.configs):
            self._set_form_enabled(True)
            self._load_form(self.configs[row])
        else:
            self._set_form_enabled(False)

    def _name_changed(self, text):
        if self._loading:
            return
        item = self.lstConfigs.currentItem()
        if item is not None:
            item.setText(text or self.tr("(unnamed)"))

    def _from_relations(self):
        derived = configs_from_relations()
        if not derived:
            QMessageBox.information(
                self, self.tr("No relations"),
                self.tr("No relations are defined in the project.\n\n"
                        "Create them under Project > Properties > Relations, "
                        "or set up a search manually with the New button."))
            return

        existing = {cfg.get("table") for cfg in self.configs}
        added = 0
        for cfg in derived:
            if cfg["table"] in existing:
                continue
            self.configs.append(cfg)
            added += 1

        self._refresh_list()
        if added:
            self._current_row = -1
            self.lstConfigs.setCurrentRow(len(self.configs) - 1)
        QMessageBox.information(
            self, self.tr("Derived from relations"),
            self.tr("Added {0} configuration(s). {1} table(s) were already "
                    "set up.").format(added, len(derived) - added))

    def _add(self):
        layer = self.cboTable.currentLayer()
        self.configs.append({
            "name": self.tr("New search"),
            "table": layer.id() if layer is not None else u"",
            "table_key": u"",
            "search_fields": [],
            "filter_expression": u"",
            "targets": [],
        })
        self._refresh_list()
        self._current_row = -1
        self.lstConfigs.setCurrentRow(len(self.configs) - 1)

    def _remove(self):
        row = self.lstConfigs.currentRow()
        if not 0 <= row < len(self.configs):
            return
        del self.configs[row]
        self._current_row = -1
        self._refresh_list()
        if self.configs:
            self.lstConfigs.setCurrentRow(min(row, len(self.configs) - 1))
        else:
            self._set_form_enabled(False)

    # -- form --------------------------------------------------------------

    def _load_form(self, cfg):
        self._loading = True
        try:
            self.txtName.setText(cfg.get("name") or u"")

            layer = resolve_layer(cfg.get("table", ""))
            if layer is not None:
                if layer.geometryType() != QgsWkbTypes.NullGeometry:
                    self.chkAllVector.setChecked(True)
                    self.cboTable.setFilters(QgsMapLayerProxyModel.VectorLayer)
                self.cboTable.setLayer(layer)
            self.cboKey.setLayer(layer)
            self.cboKey.setField(cfg.get("table_key") or u"")
            self.expFilter.setLayer(layer)
            self.expFilter.setExpression(cfg.get("filter_expression") or u"")

            self._populate_fields(layer, cfg.get("search_fields") or [])
            self._populate_targets(cfg)
        finally:
            self._loading = False

    def _store_form(self, cfg):
        cfg["name"] = self.txtName.text().strip() or u"(uden navn)"
        layer = self.cboTable.currentLayer()
        cfg["table"] = layer.id() if layer is not None else u""
        cfg["table_key"] = self.cboKey.currentField() or u""
        cfg["filter_expression"] = (
            self.expFilter.expression() if self.expFilter.isValidExpression() else u"")

        fields = []
        for row in range(self.lstFields.count()):
            item = self.lstFields.item(row)
            if item.checkState() == Qt.Checked:
                fields.append(item.data(Qt.UserRole))
        cfg["search_fields"] = fields

        targets = []
        for row in range(self.tblTargets.rowCount()):
            item = self.tblTargets.item(row, 0)
            if item is None or item.checkState() != Qt.Checked:
                continue
            combo = self.tblTargets.cellWidget(row, 1)
            field = combo.currentText() if combo is not None else u""
            targets.append({"layer": item.data(Qt.UserRole), "key": field})
        cfg["targets"] = targets

    def _populate_fields(self, layer, selected):
        self.lstFields.clear()
        if layer is None:
            return
        chosen = set(selected)
        for field in layer.fields():
            label = field.name()
            if field.alias():
                label = u"{}  ({})".format(field.name(), field.alias())
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, field.name())
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if field.name() in chosen else Qt.Unchecked)
            self.lstFields.addItem(item)

    def _add_target_row(self, label, layer_id, field_names, selected,
                        checked, tooltip=None, enabled=True):
        """Add one row: a check box with the layer name plus a key field picker."""
        row = self.tblTargets.rowCount()
        self.tblTargets.insertRow(row)

        item = QTableWidgetItem(label)
        item.setData(Qt.UserRole, layer_id)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        if tooltip:
            item.setToolTip(tooltip)
        self.tblTargets.setItem(row, 0, item)

        combo = QComboBox(self.tblTargets)
        combo.addItems(field_names)
        if selected:
            index = combo.findText(selected)
            if index < 0:
                # a stored field name absent from the layer: show it anyway,
                # so the setup is not quietly changed
                combo.insertItem(0, selected)
                index = 0
            combo.setCurrentIndex(index)
        combo.setEnabled(enabled)
        combo.setToolTip(
            self.tr("The field in this layer that links to the key field of "
                    "the table. The two fields need not have the same "
                    "name."))
        self.tblTargets.setCellWidget(row, 1, combo)

    @staticmethod
    def _guess_target_field(layer, key):
        """Guess which field in the target layer matches the table key field.

        First the same name, then the same name ignoring case, and finally the
        name without a leading "parent" or "fk_" - ParentGlobalId typically
        points at GlobalID. The guess is only a suggestion: the row is not
        checked beforehand, so a wrong guess does no harm.
        """
        if not key:
            return u""
        names = [field.name() for field in layer.fields()]
        if key in names:
            return key
        lowered = {name.lower(): name for name in names}
        candidates = [key.lower()]
        for prefix in ("parent", "fk_", "fk"):
            if key.lower().startswith(prefix) and len(key) > len(prefix):
                candidates.append(key[len(prefix):].lstrip("_").lower())
        for candidate in candidates:
            if candidate in lowered:
                return lowered[candidate]
        return u""

    def _populate_targets(self, cfg):
        """List the layers with geometry, letting the user pick a field per layer.

        The fields on the two sides need not share a name - in an Esri model
        they are typically GlobalID in the parent and ParentGlobalId in the
        child. Every layer with geometry is therefore listed, and the field is
        chosen in the drop-down rather than derived from the name. A guess is
        preselected, but the row is only checked if the layer is already in the
        setup.

        Target layers from the setup that are absent from the project right now
        appear at the top, checked. Otherwise they would drop out of the setup
        merely because the dialog was opened with the layer switched off - this
        table is what _store_form() builds the new target list from.
        """
        self.tblTargets.setRowCount(0)
        key = self.cboKey.currentField() or cfg.get("table_key") or u""
        table_layer = self.cboTable.currentLayer()
        chosen = {t.get("layer"): t.get("key") for t in cfg.get("targets", [])}

        missing = 0
        for target in cfg.get("targets", []):
            layer_id = target.get("layer", "")
            if not layer_id or resolve_layer(layer_id) is not None:
                continue
            stored = target.get("key", "")
            self._add_target_row(
                self.tr("{0}  (missing from the project)").format(layer_id),
                layer_id,
                [stored] if stored else [], stored, True,
                tooltip=self.tr(
                    "The layer is not loaded in the project right now. It is "
                    "kept in the setup, so it still works once the layer is "
                    "back. Clear the check box to delete the target layer for "
                    "good."),
                enabled=False)
            missing += 1

        candidates = 0
        for layer in QgsProject.instance().mapLayers().values():
            if not hasattr(layer, "fields"):
                continue
            if table_layer is not None and layer.id() == table_layer.id():
                continue
            if layer.geometryType() == QgsWkbTypes.NullGeometry:
                continue
            names = [field.name() for field in layer.fields()]
            if not names:
                continue
            configured = chosen.get(layer.id())
            selected = configured or self._guess_target_field(layer, key)
            self._add_target_row(
                layer.name(), layer.id(), names, selected,
                layer.id() in chosen)
            candidates += 1

        if candidates == 0 and missing == 0:
            self.lblTargetHint.setText(
                self.tr("There are no layers with geometry in the project."))
        else:
            hint = (self.tr("Check the layers to search, and pick the field "
                            "in the layer that matches '{0}'. The fields need "
                            "not have the same name.").format(key) if key else
                    self.tr("Pick a key field in the table first."))
            if missing:
                hint += self.tr(
                    " {0} target layer(s) in the setup are not loaded right "
                    "now; they are checked at the top and will be "
                    "kept.").format(missing)
            self.lblTargetHint.setText(hint)

    # -- reactions ---------------------------------------------------------

    def _all_vector_toggled(self, enabled):
        self.cboTable.setFilters(
            QgsMapLayerProxyModel.VectorLayer if enabled
            else QgsMapLayerProxyModel.NoGeometry)

    def _table_changed(self, layer):
        if self._loading:
            return
        self.cboKey.setLayer(layer)
        self.expFilter.setLayer(layer)
        self._populate_fields(layer, [])
        if 0 <= self._current_row < len(self.configs):
            self._populate_targets(self.configs[self._current_row])

    def _key_changed(self, _field):
        if self._loading:
            return
        if 0 <= self._current_row < len(self.configs):
            cfg = self.configs[self._current_row]
            self._store_form(cfg)
            self._populate_targets(cfg)

    # -- finishing ---------------------------------------------------------

    def accept(self):
        if 0 <= self._current_row < len(self.configs):
            self._store_form(self.configs[self._current_row])

        problems = []
        for cfg in self.configs:
            usable, issues = validate_config(cfg)
            if not usable:
                problems.append(u"• {}: {}".format(
                    cfg.get("name"), u"; ".join(issues)))

        if problems:
            answer = QMessageBox.warning(
                self, self.tr("Incomplete setup"),
                self.tr("The following configurations cannot be used:"
                        "\n\n{0}\n\nSave anyway?").format(
                            u"\n".join(problems)),
                QMessageBox.Save | QMessageBox.Cancel)
            if answer != QMessageBox.Save:
                return

        save_configs(self.configs)
        super(ConfigDialog, self).accept()
