def test_sanity():
    assert 1 == 1


def test_qml_engine_loads_timer_overlay(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    from lazynote import store
    from lazynote.app import create_engine

    monkeypatch.setattr(store, "_LEGACY_DB_PATHS", [])
    app = QApplication.instance() or QApplication([])
    engine = create_engine(app)
    assert engine.rootObjects()
