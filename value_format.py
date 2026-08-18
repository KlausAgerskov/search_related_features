# -*- coding: utf-8 -*-
"""
value_format.py
---------------
Turns stored field values into the text shown to the user.

Many tables store codes rather than text and leave the display to a value map
(ValueMap): the field holds `graesning`, say, but should read "Grazing".
Without that translation the panel would show raw codes in both the table and
the filters.

The translation goes through the field formatters of QGIS - the same mechanism
the attribute table uses - so ValueMap, ValueRelation, Range, DateTime and
CheckBox are handled without the plugin having to interpret the setup itself.
"""

from qgis.core import QgsApplication

from .project_config import log


def raw_text(value):
    """A consistent text form of a raw value, used as a key in filters."""
    if value is None:
        return u""
    return u"{}".format(value)


class ValueFormatter(object):
    """Turns raw field values into displayed text for one layer.

    The formatter is looked up once per field, and the result is memoised per
    value, so a table with many rows does not cost one lookup per cell.
    """

    def __init__(self, layer):
        self.layer = layer
        self._setups = {}       # field index -> (formatter, config, cache)
        self._memo = {}         # (field index, raw text) -> displayed text

    # -- internal ----------------------------------------------------------

    def _setup(self, field_index):
        if field_index in self._setups:
            return self._setups[field_index]

        formatter = None
        config = {}
        cache = None
        try:
            setup = self.layer.editorWidgetSetup(field_index)
            config = setup.config()
            registry = QgsApplication.fieldFormatterRegistry()
            formatter = registry.fieldFormatter(setup.type())
            if formatter is not None:
                # ValueRelation looks up another layer; build the cache once
                cache = formatter.createCache(self.layer, field_index, config)
        except Exception as error:            # pylint: disable=broad-except
            log(u"Could not get field formatter for {} field {}: {}".format(
                self.layer.name(), field_index, error))
            formatter = None

        self._setups[field_index] = (formatter, config, cache)
        return self._setups[field_index]

    # -- public ------------------------------------------------------------

    def has_lookup(self, field_index):
        """True if the field has a value map, meaning the stored value and the
        displayed text can differ."""
        try:
            return self.layer.editorWidgetSetup(field_index).type() in (
                "ValueMap", "ValueRelation")
        except Exception:                     # pylint: disable=broad-except
            return False

    def label(self, field_index, value):
        """Displayed text for a raw value. Empty string for NULL."""
        if value is None:
            return u""

        text = raw_text(value)
        memo_key = (field_index, text)
        if memo_key in self._memo:
            return self._memo[memo_key]

        formatter, config, cache = self._setup(field_index)
        label = text
        if formatter is not None:
            try:
                shown = formatter.representValue(
                    self.layer, field_index, config, cache, value)
                if shown is not None:
                    shown = u"{}".format(shown).strip()
                    # the formatter returns NULL markers for empty values
                    if shown and shown.upper() not in ("NULL", "(NULL)"):
                        label = shown
            except Exception as error:        # pylint: disable=broad-except
                log(u"Field formatter failed on {} field {}: {}".format(
                    self.layer.name(), field_index, error))

        self._memo[memo_key] = label
        return label

    def sort_value(self, value, label):
        """The value the table sorts on: numbers as numbers, else text."""
        if value is None:
            return u""
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        try:
            return float(raw_text(value))
        except (TypeError, ValueError):
            return label.lower()
