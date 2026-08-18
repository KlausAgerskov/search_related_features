# -*- coding: utf-8 -*-
"""
project_config.py
-----------------
Reading and writing the plugin setup in the project file, plus helpers for
looking up layers and normalising key values.

The setup lives as a project property under the scope "search_related_features",
serialised as JSON. It therefore ends up in <properties> in the .qgs file
inside the .qgz archive and travels with the project template.

Schema (a list of dicts):

    {
      "name":          "<name in the drop-down>",
      "table":         "<layer id or name>",   # the table searched in
      "table_key":     "<field name>",         # the field linked on
      "search_fields": ["<field name>", ...],  # columns shown and searched
      "filter_expression": "<expression>",     # optional, empty = all rows
      "targets": [
          {"layer": "<layer id or name>", "key": "<field name>"},
          {"layer": "<layer id or name>", "key": "<field name>"}
      ]
    }

An empty "search_fields" means every column in the table.
"""

import json

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeatureRequest, QgsMessageLog, Qgis,
    QgsSettings,
)

try:
    from qgis.PyQt import sip
except ImportError:                           # ældre PyQt-udgaver
    import sip

def _tr(text):
    """Translate a string. QCoreApplication.translate is used directly here
    because translation.py takes log() from this module - importing the other
    way round would be a circular import."""
    return QCoreApplication.translate("ProjectConfig", text)


PLUGIN_NAME = "Search Related Features"
PROJECT_SCOPE = "search_related_features"
CONFIG_ENTRY = "searchConfigs"


# Fields in a stored setup that do not exist in the actual table are dropped
# automatically on load. A setup may therefore name columns that only exist in
# some of the tables - two spellings of the same field name, say - without
# that being an error.


# --------------------------------------------------------------------------
# compatibility
# --------------------------------------------------------------------------

def no_geometry_flag():
    """QgsFeatureRequest.NoGeometry is called Flag.NoGeometry from QGIS 3.36."""
    flag = getattr(QgsFeatureRequest, "Flag", None)
    if flag is not None and hasattr(flag, "NoGeometry"):
        return flag.NoGeometry
    return QgsFeatureRequest.NoGeometry


def log(message, level=Qgis.Info):
    QgsMessageLog.logMessage(u"{}".format(message), PLUGIN_NAME, level)


def is_alive(obj):
    """True if the Python object still has a live C++ object behind it.

    When a new project opens, QGIS deletes the old layers in C++. A stored
    reference then points at a deleted object, and even reading a property from
    it raises "wrapped C/C++ object ... has been deleted".
    """
    if obj is None:
        return False
    try:
        return not sip.isdeleted(obj)
    except (TypeError, AttributeError):
        return True


# --------------------------------------------------------------------------
# key values
# --------------------------------------------------------------------------

def normalize_key(value):
    """Normalise a key value to a trimmed string.

    Ensures that text/number differences between the two sides of a relation do
    not cause silent mismatches. Returns None for NULL and empty values.
    """
    if value is None:
        return None
    try:
        if isinstance(value, float) and value.is_integer():
            value = int(value)
    except (TypeError, ValueError):
        pass
    text = u"{}".format(value).strip()
    if not text or text.upper() == "NULL":
        return None
    return text


# --------------------------------------------------------------------------
# layer lookup
# --------------------------------------------------------------------------

def resolve_layer(ident):
    """Look up a layer by id, else by name. Returns a valid vector layer or
    None."""
    if not ident:
        return None
    project = QgsProject.instance()
    layer = project.mapLayer(ident)
    if layer is None:
        matches = project.mapLayersByName(ident)
        layer = matches[0] if matches else None
    if isinstance(layer, QgsVectorLayer) and layer.isValid():
        return layer
    return None


def all_field_names(layer):
    """Every field name in a layer, in table order. Empty if the layer is gone."""
    if layer is None:
        return []
    return [field.name() for field in layer.fields()]


def layer_label(ident):
    """A readable name for use in dialogs and log messages."""
    layer = resolve_layer(ident)
    return (layer.name() if layer is not None
            else _tr("{0} (missing)").format(ident))


# --------------------------------------------------------------------------
# read / write
# --------------------------------------------------------------------------

def load_configs():
    """Read the setup from the current project. Returns a list."""
    raw, ok = QgsProject.instance().readEntry(PROJECT_SCOPE, CONFIG_ENTRY, "")
    if not ok or not raw:
        return []
    try:
        configs = json.loads(raw)
    except (ValueError, TypeError):
        log(u"Could not read the setup from the project (invalid JSON)",
            Qgis.Warning)
        return []
    if not isinstance(configs, list):
        return []
    for cfg in configs:
        # accept the earlier single-target format
        if "targets" not in cfg and "target" in cfg:
            cfg["targets"] = [{
                "layer": cfg["target"],
                "key": cfg.get("target_key", cfg.get("table_key")),
            }]
        cfg.setdefault("targets", [])
        cfg.setdefault("search_fields", [])
        cfg.setdefault("filter_expression", "")
    return configs


def save_configs(configs):
    """Write the setup into the current project (.qgz)."""
    project = QgsProject.instance()
    project.writeEntry(PROJECT_SCOPE, CONFIG_ENTRY,
                       json.dumps(configs, ensure_ascii=False))
    project.setDirty(True)
    log(u"Saved {} config(s) in the project".format(len(configs)))


def clear_configs():
    """Remove the setup from the project."""
    project = QgsProject.instance()
    project.removeEntry(PROJECT_SCOPE, CONFIG_ENTRY)
    project.setDirty(True)


# --------------------------------------------------------------------------
# remembered column filters
# --------------------------------------------------------------------------
#
# Which columns you filter on is a working habit, not a property of the
# project: the same user tends to filter on the same columns every time, while
# a colleague uses others. It is therefore stored in QgsSettings for the user
# and not in the .qgz file.
#
# Only the columns are remembered. The checked values are not, so the panel
# always opens with every row visible.

def _facet_key(cfg):
    """A key that survives a configuration being renamed."""
    return cfg.get("table") or cfg.get("name") or u""


def load_facet_columns(cfg):
    """Field names of the column filters last used for this configuration."""
    key = _facet_key(cfg)
    if not key:
        return []
    raw = QgsSettings().value(
        u"{}/facetColumns/{}".format(PROJECT_SCOPE, key), u"", type=str)
    if not raw:
        return []
    try:
        names = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def save_facet_columns(cfg, names):
    """Remember which columns are filtered on. Value choices deliberately not."""
    key = _facet_key(cfg)
    if not key:
        return
    QgsSettings().setValue(
        u"{}/facetColumns/{}".format(PROJECT_SCOPE, key),
        json.dumps(list(names), ensure_ascii=False))


# --------------------------------------------------------------------------
# derive from relations
# --------------------------------------------------------------------------

def configs_from_relations(search_fields=None):
    """Derive a setup from the relations of the project.

    Relations are grouped by the referencing (child) layer, so a table with two
    relations becomes one configuration with two target layers.

    Without `search_fields`, every column of the table is included. If there
    are many, trim them afterwards in the settings dialog.

    Layers are stored by id, so the setup survives a layer being renamed.
    """
    project = QgsProject.instance()
    grouped = {}

    for relation in project.relationManager().relations().values():
        child = relation.referencingLayer()
        parent = relation.referencedLayer()
        if child is None or parent is None:
            continue
        pairs = relation.fieldPairs()   # {referencing field: referenced field}
        if not pairs:
            continue
        child_field = list(pairs.keys())[0]
        parent_field = list(pairs.values())[0]

        cfg = grouped.setdefault(child.id(), {
            "name": child.name(),
            "table": child.id(),
            "table_key": child_field,
            "search_fields": (list(search_fields) if search_fields
                              else all_field_names(child)),
            "filter_expression": "",
            "targets": [],
        })
        if not any(t.get("layer") == parent.id() for t in cfg["targets"]):
            cfg["targets"].append({"layer": parent.id(), "key": parent_field})

    return list(grouped.values())


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

def validate_config(cfg):
    """Check that layers and fields exist in the current project.

    The setup is not modified. Target layers that cannot be used are listed
    among the problems but stay in the setup: a layer that failed to load this
    time - because the service was down, or because the layer was switched off
    - must not disappear from the .qgz file the next time the setup is saved.
    During selection they are skipped instead (see
    SearchPanel._select_in_targets).

    Returns (usable: bool, problems: list of texts). Usable means the table,
    the key field and at least one target layer can be used right now.
    """
    problems = []

    table = resolve_layer(cfg.get("table", ""))
    if table is None:
        problems.append(_tr("The table '{0}' is not in the project").format(
            cfg.get("table", "")))
        return False, problems

    key = cfg.get("table_key", "")
    if table.fields().lookupField(key) < 0:
        problems.append(_tr("The field '{0}' is not in {1}").format(
            key, table.name()))
        return False, problems

    usable = 0
    for target in cfg.get("targets", []):
        layer = resolve_layer(target.get("layer", ""))
        if layer is None:
            problems.append(
                _tr("The target layer '{0}' is missing - skipped").format(
                    target.get("layer", "")))
            continue
        if layer.fields().lookupField(target.get("key", "")) < 0:
            problems.append(
                _tr("The field '{0}' is not in {1} - the layer is "
                    "skipped").format(target.get("key", ""), layer.name()))
            continue
        usable += 1

    if not usable:
        problems.append(_tr("No usable target layers"))
        return False, problems

    return True, problems
