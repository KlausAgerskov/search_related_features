# -*- coding: utf-8 -*-
"""
key_index.py
------------
Key lookups from a table row to a polygon.

Where the target layers sit on a remote source - arcgisfeatureserver, WFS, a
database across the network - a filter expression per click would mean a call
out to the server every time the selection changes, and in the worst case a
fetch of the entire layer. Two routes avoid that: small key sets go straight at
the layer with an IN expression, while larger ones build a
{key: [feature id]} index once per layer per session.

Both caches are cleared automatically when the layer is edited.
"""

import time

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QGuiApplication, QCursor
from qgis.core import QgsFeatureRequest, QgsProject, QgsExpression, Qgis

from .project_config import normalize_key, no_geometry_flag, log, is_alive

# Up to this many keys are looked up with an IN expression rather than building
# the whole index. A single click in the table then costs one small query
# instead of fetching the entire layer. Set to 0 to always build the index.
EXPRESSION_LIMIT = 200

# Keys per query. An IN expression with thousands of values turns into a URL or
# SQL statement the server rejects, so they are split into portions.
EXPRESSION_CHUNK = 100


def _literal(value, numeric):
    """A key value as it should appear in an expression. None if unusable."""
    text = u"{}".format(value)
    if not numeric:
        return QgsExpression.quotedValue(text)
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return u"{}".format(int(number)) if number.is_integer() else repr(number)


class KeyIndex(object):
    """Cache of {normalised key: [feature id]} per (layer, field)."""

    def __init__(self):
        self._cache = {}
        self._partial = {}      # (layer, field) -> {key: [fid]} from expression lookups
        self._connected = {}

    # -- public ------------------------------------------------------------

    def get(self, layer, field):
        """The index for (layer, field). Built the first time it is used."""
        cache_key = (layer.id(), field)
        if cache_key in self._cache:
            return self._cache[cache_key]
        table = self._build(layer, field)
        self._cache[cache_key] = table
        self._watch(layer)
        return table

    def lookup(self, layer, field, values):
        """Look up a list of key values. Returns a list of feature ids.

        If the index has not been built yet and there are few keys, the layer
        is queried directly with an IN expression. That is what makes the first
        selection fast: without it the whole layer has to be fetched before
        anything can be selected. Many keys at once, on the other hand, pay for
        a full index, so one is built.
        """
        values = list(values)
        if not values:
            return []

        cache_key = (layer.id(), field)
        if cache_key not in self._cache and 0 < len(values) <= EXPRESSION_LIMIT:
            fids = self._lookup_by_expression(layer, field, values)
            if fids is not None:
                return fids

        table = self.get(layer, field)
        return self._collect(values, table)

    @staticmethod
    def _collect(values, table):
        """Collect feature ids in key order, without duplicates."""
        fids = []
        seen = set()
        for value in values:
            for fid in table.get(value, []):
                if fid not in seen:
                    seen.add(fid)
                    fids.append(fid)
        return fids

    def clear(self):
        """Clear the whole cache, for instance when a new project opens."""
        self._cache = {}
        self._partial = {}
        self._disconnect_all()

    def invalidate(self, layer_id):
        """Clear the cache for a single layer."""
        for cache_key in [k for k in self._cache if k[0] == layer_id]:
            del self._cache[cache_key]
        for cache_key in [k for k in self._partial if k[0] == layer_id]:
            del self._partial[cache_key]

    # -- internal ----------------------------------------------------------

    def _lookup_by_expression(self, layer, field, values):
        """Query the layer directly with one IN expression per portion of keys.

        Returns a list of feature ids, or None if the lookup could not be
        carried out - the caller then falls back to the full index.

        The answers are remembered per key, including the empty ones, so the
        same click twice in a row costs one query.
        """
        index = layer.fields().lookupField(field)
        if index < 0:
            log(u"Field {} not found in {}".format(field, layer.name()))
            return []

        numeric = layer.fields().at(index).isNumeric()
        known = self._partial.setdefault((layer.id(), field), {})
        missing = [value for value in values if value not in known]

        if missing:
            started = time.time()
            QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            try:
                for start in range(0, len(missing), EXPRESSION_CHUNK):
                    portion = missing[start:start + EXPRESSION_CHUNK]
                    literals = [_literal(value, numeric) for value in portion]
                    literals = [lit for lit in literals if lit is not None]
                    if not literals:
                        continue
                    expression = u"{} IN ({})".format(
                        QgsExpression.quotedColumnRef(field),
                        u", ".join(literals))
                    request = QgsFeatureRequest()
                    request.setFilterExpression(expression)
                    request.setSubsetOfAttributes([index])
                    request.setFlags(no_geometry_flag())
                    for feature in layer.getFeatures(request):
                        # normalise again: the server may match regardless of
                        # case or surrounding whitespace
                        key = normalize_key(feature[index])
                        if key is not None:
                            known.setdefault(key, [])
                            if feature.id() not in known[key]:
                                known[key].append(feature.id())
                    for value in portion:
                        known.setdefault(value, [])
            except Exception as error:        # pylint: disable=broad-except
                log(u"Direct lookup on {}.{} failed ({}) - building index "
                    u"instead".format(layer.name(), field, error), Qgis.Warning)
                return None
            finally:
                QGuiApplication.restoreOverrideCursor()

            log(u"Looked up {} key(s) directly on {}.{} in {:.1f} s".format(
                len(missing), layer.name(), field, time.time() - started))

        return self._collect(values, known)

    def _build(self, layer, field):
        index = layer.fields().lookupField(field)
        if index < 0:
            log(u"Field {} not found in {}".format(field, layer.name()))
            return {}

        request = QgsFeatureRequest()
        request.setSubsetOfAttributes([index])
        request.setFlags(no_geometry_flag())

        table = {}
        started = time.time()
        QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            for feature in layer.getFeatures(request):
                key = normalize_key(feature[index])
                if key is not None:
                    table.setdefault(key, []).append(feature.id())
        finally:
            QGuiApplication.restoreOverrideCursor()

        log(u"Indexed {} keys on {}.{} in {:.1f} s".format(
            len(table), layer.name(), field, time.time() - started))
        return table

    def _watch(self, layer):
        """Listen for changes, so the index is cleared when the layer is edited."""
        layer_id = layer.id()
        if layer_id in self._connected:
            return

        def on_changed(*_args, layer_id=layer_id):
            self.invalidate(layer_id)

        handlers = []
        for signal_name in ("dataChanged", "featureAdded", "featuresDeleted",
                            "attributeValueChanged", "editingStopped",
                            "committedFeaturesAdded"):
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue
            try:
                signal.connect(on_changed)
                handlers.append((signal_name, on_changed))
            except (TypeError, AttributeError):
                pass

        # Only the layer id is stored, not the layer itself. When a new project
        # opens, QGIS deletes the old layers in C++, and a stored Python
        # reference then points at a deleted object. Merely reading a signal
        # from it raises "wrapped C/C++ object of type QgsVectorLayer has been
        # deleted".
        self._connected[layer_id] = handlers

    def _disconnect_all(self):
        """Disconnect again, skipping layers that no longer exist.

        Qt disconnects by itself when the sender is destroyed, so a vanished
        layer needs no cleanup - it just must not be touched.
        """
        project = QgsProject.instance()
        for layer_id, handlers in list(self._connected.items()):
            layer = project.mapLayer(layer_id)
            if not is_alive(layer):
                continue
            for signal_name, handler in handlers:
                try:
                    signal = getattr(layer, signal_name, None)
                    if signal is not None:
                        signal.disconnect(handler)
                except (RuntimeError, TypeError, AttributeError):
                    pass
        self._connected = {}
