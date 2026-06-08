import unittest

from utils.imagedataurl import parse_image_data_url


class TestParseImageDataUrl(unittest.TestCase):
    def test_valid_image_data_url(self):
        result = parse_image_data_url(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGP8z8AARwMCApX2FZkAAAAASUVORK5CYII="
        )
        self.assertEqual(result.mime_type, "image/png")
        self.assertEqual(
            result.data,
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGP8z8AARwMCApX2FZkAAAAASUVORK5CYII=",
        )

    def test_invalid_url_raises(self):
        with self.assertRaises(ValueError):
            parse_image_data_url("invalid")
        with self.assertRaises(ValueError):
            parse_image_data_url("data:image/png;base64")


if __name__ == "__main__":
    unittest.main()
