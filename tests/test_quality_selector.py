import unittest
from app.download_support import profile_format_selector
from app.tiktok_download import _matches_download_profile


def video(name, width, height, fps, ext='mp4', audio='aac'):
    return {'format_id': name, 'width': width, 'height': height, 'fps': fps,
            'ext': ext, 'vcodec': 'h264', 'acodec': audio, 'protocol': 'https'}


def select(quality, fps, formats, *, tiktok=False):
    selector = profile_format_selector(quality, fps, 'mp4', tiktok)
    return list(selector({'formats': formats, 'incomplete_formats': False}))


class ProfileSelectorTests(unittest.TestCase):
    def test_tiktok_unknown_fps_does_not_hide_full_hd(self):
        result = select('1080', '60', [video('hd',1080,1920,None), video('low',720,1280,30)], tiktok=True)
        self.assertEqual(result[0]['format_id'], 'hd')

    def test_tiktok_tie_prefers_bitrate_not_extractor_order(self):
        high = dict(video('high',1080,1920,60), tbr=4200)
        low = dict(video('low',1080,1920,60), tbr=1900)
        result = select('1080','60',[high,low],tiktok=True)
        self.assertEqual(result[0]['format_id'], 'high')
    def test_tiktok_combined_fullhd_beats_lower_combined(self):
        result = select('1080', '60', [video('low',576,1024,30), video('high',1080,1920,60)], tiktok=True)
        self.assertEqual(result[0]['format_id'], 'high')

    def test_profile_rejects_all_known_oversized_or_high_fps(self):
        self.assertEqual(select('720','30',[video('too-high',1080,1920,60)]), [])

    def test_best_prefers_higher_video_over_mp4_extension(self):
        audio = {'format_id':'audio','ext':'m4a','vcodec':'none','acodec':'aac','protocol':'https'}
        result = select('best','best',[audio, video('mp4-1080',1920,1080,30,audio='none'),video('webm-2160',3840,2160,30,ext='webm',audio='none')])
        self.assertEqual(result[0]['requested_formats'][0]['format_id'], 'webm-2160')
        self.assertEqual(result[0]['requested_formats'][1]['format_id'], 'audio')

    def test_best_prefers_resolution_over_extractor_quality_order(self):
        # yt-dlp normally sorts extractor quality before resolution; emulate
        # that ordering (higher-quality 720p comes last in the input).
        high = dict(video('high-res', 3840, 2160, 30), quality=0)
        low = dict(video('low-res', 1280, 720, 60), quality=10)
        result = select('best', 'best', [high, low])
        self.assertEqual(result[0]['format_id'], 'high-res')

    def test_same_resolution_prefers_higher_fps_within_profile(self):
        fast = video('fast', 1920, 1080, 60)
        slow = video('slow', 1920, 1080, 30)
        result = select('1080', '60', [fast, slow])
        self.assertEqual(result[0]['format_id'], 'fast')

    def test_tiktok_external_source_respects_profile(self):
        self.assertFalse(_matches_download_profile({'width':1080,'height':1920,'fps':60},{'download_quality':'720','fps_limit':'30'}))
        self.assertTrue(_matches_download_profile({'width':720,'height':1280,'fps':30},{'download_quality':'720','fps_limit':'30'}))
