import os
from urllib.parse import urlsplit
from yt_dlp.postprocessor.common import PostProcessor
from app.download_utils import YtDlpLogCollector
from app.logger import logger

class PlaylistResultCollector(PostProcessor):
    """Capture yt-dlp's final path and identity, not a download progress event."""
    def __init__(self):
        super().__init__()
        self.results = []

    def run(self, info):
        self.results.append((info.get('playlist_index'), info.get('id'), info.get('filepath')))
        return [], info


class PlaylistRecoveryMixin:
    def _setup_playlist_tracking(self, ydl, entries, unavailable):
        """Isolate each position only when its identity can be checked."""
        if unavailable or self.settings.get('download_type', 'video') not in {'video', 'audio'}:
            return None
        expected = {}
        for position, entry in enumerate(entries, 1):
            index = entry.get('playlist_index') or position
            identifier = entry.get('id')
            if not isinstance(index, int) or index < 1 or not identifier or index in expected or str(identifier) in expected.values():
                return None
            expected[index] = str(identifier)
        if not expected or not hasattr(ydl, 'add_post_processor'):
            return None
        templates = ydl.params.get('outtmpl')
        template = templates.get('default') if isinstance(templates, dict) else templates
        stage = os.path.abspath(self._work_dir())
        if not isinstance(template, str) or os.path.commonpath([stage, os.path.abspath(template)]) != stage:
            return None
        relative = os.path.relpath(template, stage)
        isolated = os.path.join(stage, '__playlist_items__', '%(playlist_index)s', relative)
        if isinstance(templates, dict):
            templates['default'] = isolated
        else:
            ydl.params['outtmpl'] = isolated
        self._isolated_playlist_stage = True
        collector = PlaylistResultCollector()
        ydl.add_post_processor(collector, when='after_move')
        return expected, collector

    def _retry_missing_playlist_items(self, ydl, tracking, valid_paths, skipped_count, reason):
        """Retry once only when every completed file has a unique verified identity."""
        if not tracking or not valid_paths or self._cancelled:
            return None
        reason_text = str(reason or '').lower()
        if any(x in reason_text for x in ('private', 'sign in', 'login', 'age-restricted', 'members-only', '429', 'too many requests', 'drm', 'cancel')):
            return None
        expected, collector = tracking
        skipped = {}
        if skipped_count:
            observed = getattr(ydl, 'skipped_archive_entries', set())
            archive_ids = getattr(ydl, 'skipped_archive_ids', set())
            # Refuse recovery unless every distinct archived ID maps to one
            # unambiguous playlist position and the preflight identity agrees.
            if len(archive_ids) != skipped_count or len(observed) != skipped_count:
                return None
            seen_archives = set()
            for archive_id, index, identifier in observed:
                if (archive_id not in archive_ids or archive_id in seen_archives
                        or index in skipped or expected.get(index) != identifier):
                    return None
                seen_archives.add(archive_id)
                skipped[index] = identifier
            if seen_archives != archive_ids:
                return None
        valid = {os.path.abspath(path) for path in valid_paths}
        completed = {}
        seen_paths = set()
        for index, identifier, filepath in collector.results:
            if not filepath or index not in expected or str(identifier) != expected[index]:
                return None
            path = os.path.abspath(filepath)
            if index in completed or path in seen_paths:
                return None
            seen_paths.add(path)
            if path in valid:
                completed[index] = path
        if set(completed.values()) != valid:
            return None
        if set(skipped).intersection(completed):
            return None
        missing = {index: value for index, value in expected.items() if index not in completed and index not in skipped}
        if not missing:
            return None
        opts = dict(ydl.params)
        # For recoverable transport/format errors retry missing positions with
        # the same bounded alternate selector used for individual downloads.
        # Do not touch the existing staging directory or already valid entries.
        if any(token in reason_text for token in ('requested format', 'http error 403', 'forbidden',
                'http error 404', 'timed out', 'timeout', 'connection reset', 'invalid audio output',
                'invalid video output')):
            previous_alternative = self._alternative_retry_used
            try:
                self._alternative_retry_used = True
                opts['format'] = self._build_ydl_opts()['format']
            finally:
                self._alternative_retry_used = previous_alternative
            if (urlsplit(self.url).hostname or '').lower() in {
                    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com'}:
                opts.pop('cookiefile', None)
                opts.pop('cookiesfrombrowser', None)
        templates = dict(opts.get('outtmpl') or {})
        stage = os.path.abspath(self._work_dir())
        prefix = os.path.join(stage, '__playlist_items__', '%(playlist_index)s')
        default = templates.get('default', '')
        if not default.startswith(prefix + os.sep):
            return None
        templates['default'] = os.path.join(prefix, '__retry__', os.path.relpath(default, prefix))
        opts['outtmpl'] = templates
        opts['playlist_items'] = ','.join(str(i) for i in sorted(missing))
        opts['match_filter'] = lambda info, *, incomplete=False: None if incomplete and not info.get('id') else (None if missing.get(info.get('playlist_index')) == str(info.get('id')) else 'Playlist item changed')
        self._ydl_logger = YtDlpLogCollector(self.item_id)
        opts['logger'] = self._ydl_logger
        retry_collector = PlaylistResultCollector()
        self.status.emit(self.item_id, 'Повторяем только незагруженные элементы плейлиста...')
        try:
            with type(ydl)(opts) as retry:
                retry.add_post_processor(retry_collector, when='after_move')
                code = retry.download([self.url])
                if code not in (None, 0) or self._ydl_logger.errors or retry.skipped_archive_ids:
                    return None
                from app.download_support import validate_video_profile
                from app.download_artifacts import validate_video_with_audio
                results = {}
                for index, identifier, path in retry_collector.results:
                    if index not in missing or str(identifier) != missing[index] or index in results or not path:
                        return None
                    path = os.path.abspath(path)
                    items_dir = os.path.join(stage, '__playlist_items__')
                    relative = os.path.relpath(path, items_dir).split(os.sep)
                    # yt-dlp may pad playlist_index (e.g. 002 in a 100-item
                    # playlist). Validate the numeric identity without assuming
                    # its rendered width, and still require the retry subtree.
                    if (len(relative) < 3 or not relative[0].isdigit()
                            or int(relative[0]) != index or relative[1] != '__retry__'
                            or not os.path.isfile(path)):
                        return None
                    if self.settings.get('download_type', 'video') == 'audio':
                        ok = self._has_complete_retry_output([path])
                    else:
                        ok = validate_video_with_audio(path)[0] and validate_video_profile(path, self.settings, self.url, self.item_id)[0]
                    if not ok:
                        return None
                    results[index] = path
                if set(results) != set(missing):
                    return None
                ydl._pending_archive.extend(retry._pending_archive)
                logger.info('[%s] stage=playlist_retry validated=%s', self.item_id, len(results))
                return list(results.values())
        except Exception:
            logger.exception('[%s] stage=playlist_retry failed', self.item_id)
            return None
