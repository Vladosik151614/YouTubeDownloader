import os
import unittest
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

from app.queue_widget import QueueWidget


class QueueThumbnailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_successful_network_reply_is_not_treated_as_error(self):
        image = QImage(3, 3, QImage.Format.Format_RGB32)
        image.fill(0xff0000)
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(image.save(buffer, 'PNG'))
        reply = Mock()
        reply.error.return_value = QNetworkReply.NetworkError.NoError
        reply.readAll.return_value = data
        widget = Mock()
        widget._thumb_requests = {reply: ('item', None, 'thumb')}
        widget._thumb_cache = {}
        QueueWidget._on_thumbnail_loaded(widget, reply)
        widget._placeholder_thumbnail.assert_not_called()
        widget._apply_thumbnail.assert_called_once()
        self.assertIn('thumb', widget._thumb_cache)

    def test_network_failure_uses_placeholder(self):
        reply = Mock()
        reply.error.return_value = QNetworkReply.NetworkError.HostNotFoundError
        reply.errorString.return_value = 'not found'
        widget = Mock()
        widget._thumb_requests = {reply: ('item', None, 'thumb')}
        QueueWidget._on_thumbnail_loaded(widget, reply)
        widget._placeholder_thumbnail.assert_called_once()
        reply.readAll.assert_not_called()
