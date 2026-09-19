import unittest
from unittest.mock import patch, Mock
from booking_locale import english_booking_url
import travelpayouts as tp


class BookingLocaleTests(unittest.TestCase):
    def test_locales_preserve_property_query_and_fragment(self):
        for source, expected in [
            ('https://www.klook.com/zh-TW/hotels/detail/123/?check_in=2026-10-10&x=a%2Fb#rooms',
             'https://www.klook.com/en-US/hotels/detail/123/?check_in=2026-10-10&x=a%2Fb#rooms'),
            ('https://m.kkday.com/ja/hotel/product/123', 'https://m.kkday.com/en/hotel/product/123'),
            ('https://www.klook.com/hotels/detail/123', 'https://www.klook.com/en-US/hotels/detail/123')]:
            self.assertEqual(english_booking_url(source), expected)
            self.assertEqual(english_booking_url(expected), expected)

    def test_unknown_tracking_and_unsafe_urls_unchanged(self):
        for url in ('https://klook.tp.st/abc', 'https://tp.st/abc',
                    'https://www.klook.com/affiliate/abc', 'https://www.klook.com/redirect?url=x',
                    'https://expedia.com/affiliate/Zc2O7FL', 'https://klook.com.evil.test/ja/hotels/',
                    'https://user@klook.com/ja/hotels/', 'https://www.klook.com:123/ja/hotels/'):
            self.assertEqual(english_booking_url(url), url)

    def test_english_destination_sent_to_tracking_api_and_original_mapped(self):
        original = 'https://www.klook.com/zh-TW/hotels/detail/123'
        destination = english_booking_url(original)
        tracked = 'https://klook.tp.st/test'
        response = Mock()
        response.json.return_value = {'result': {'links': [dict(url=destination, partner_url=tracked, code='success')]}}
        tp._cache.clear()
        with patch('travelpayouts.configuration', return_value=('fake', 1, 2)), patch('travelpayouts.requests.post', return_value=response) as post:
            self.assertEqual(tp.convert_hotel_links([original]), {original: tracked})
            self.assertEqual(post.call_args.kwargs['json']['links'][0]['url'], destination)
        tp._cache.clear()

    def test_untracked_fallback_is_also_english(self):
        with patch('travelpayouts.configuration', return_value=None):
            result = tp.monetize_hotel_markdown('[Klook](https://www.klook.com/ko/hotels/detail/123)')
        self.assertIn('https://www.klook.com/en-US/hotels/detail/123', result)
        self.assertNotIn('may earn a commission', result)
